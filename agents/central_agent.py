from langchain_core.prompts import PromptTemplate
from integrations.issue_mapper import preparar_payload_central
from agents import cargar_prompt
from core.llm_factory import obtener_llm_para_agente
from core.performance_audit import (
    auditar_llamada_agente, registrar_evento_grafo, registrar_motivo_reparacion,
    registrar_evento_sublote_central, registrar_sublote_central,
    registrar_integridad_central,
)
from core.batch_contract import (
    calcular_num_predict, normalizar_iid, normalizar_presentacion_requerimientos,
    normalizar_requerimientos_propuestos_gap,
)
from core.config import OLLAMA_MODEL
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

_SSL_PATH_VARIABLES = (
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "HTTPX_CA_BUNDLE",
)


def _es_ollama_http_local(base_url: str) -> bool:
    normalized = str(base_url or "").strip().casefold()
    return normalized.startswith("http://localhost") or normalized.startswith("http://127.0.0.1")


@contextmanager
def _entorno_ssl_local_ollama(base_url: str):
    """Aparta rutas CA inexistentes solo mientras se construye Ollama HTTP local."""
    removed: Dict[str, str] = {}
    if _es_ollama_http_local(base_url):
        for name in _SSL_PATH_VARIABLES:
            value = os.environ.get(name)
            if value and not os.path.exists(value):
                removed[name] = value
                os.environ.pop(name, None)
                logger.warning("OLLAMA_LOCAL_SSL_PATH_IGNORED variable=%s path_exists=false", name)
    try:
        yield tuple(removed)
    finally:
        os.environ.update(removed)


def crear_cliente_ollama_central(
    cache: Dict[tuple, Any], *, num_predict: int, num_ctx: int = 8192,
    temperature: float = 0.1, json_mode: bool = True,
) -> Any:
    """Crea como máximo un cliente por configuración durante una ejecución Central."""
    from core.config import OLLAMA_BASE_URL

    key = (
        OLLAMA_MODEL,
        OLLAMA_BASE_URL,
        num_predict,
        num_ctx,
        temperature,
        json_mode,
    )

    if key not in cache:
        with _entorno_ssl_local_ollama(OLLAMA_BASE_URL) as ignored:
            selection = obtener_llm_para_agente(
                "central",
                json_mode=json_mode,
                num_predict=num_predict,
                num_ctx=num_ctx,
                temperature=temperature,
            )
            cache[key] = selection.llm

        registrar_evento_grafo(
            "central_ollama_client_created",
            "Central_Init",
            model=OLLAMA_MODEL,
            num_predict=num_predict,
            num_ctx=num_ctx,
            ssl_variables_ignored=list(ignored),
        )

    return cache[key]

def procesar_ticket(project_name: str, issues_json_str: str, sprint_context: str, num_predict_override: int | None = None, llm_override: Any = None) -> str:
    """
    Agente Central: Orquesta el inicio procesando un lote de historias.
    Analiza el texto de los requerimientos de múltiples historias y confirma la recepción generando un JSON estructurado (Array).
    """
    issues = json.loads(issues_json_str)
    expected_issue_ids = []
    for item in issues:
        raw_iid = item.get("issue_iid")
        if raw_iid is None:
            raw_iid = item.get("id")
        iid = normalizar_iid(raw_iid)
        if iid is None:
            raise ValueError("CENTRAL_INPUT_WITHOUT_ISSUE_IID")
        expected_issue_ids.append(iid)
    num_predict = num_predict_override or calcular_num_predict("Central_Init", len(expected_issue_ids))
    if llm_override is not None:
        llm = llm_override
        provider = "ollama"
        model = OLLAMA_MODEL
    else:
        selection = obtener_llm_para_agente(
            "central",
            json_mode=True,
            num_predict=num_predict,
            num_ctx=8192,
            temperature=0.1,
        )

        llm = selection.llm
        provider = selection.provider
        model = selection.model
    prompt_template = cargar_prompt("central_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        issues_json_str=issues_json_str,
        sprint_context=sprint_context,
        expected_issue_ids=json.dumps(expected_issue_ids),
    )
    
    params = {
        "provider": provider,
        "model": model,
        "json_mode": True,
        "num_predict": num_predict,
        "num_ctx": 8192,
        "temperature": 0.1,
    }
    
    with auditar_llamada_agente(
        "Central_Init_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        model_params=params,
    ) as audit:
        from core.remote_execution import REMOTE_PACER, reintentar_con_backoff
        if provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(provider, "Central")
        try:
            invoke_fn = lambda: chain.invoke({
                "project_name": project_name,
                "issues_json_str": issues_json_str,
                "sprint_context": sprint_context,
                "expected_issue_ids": json.dumps(expected_issue_ids),
            })
            if provider == "nvidia":
                response = reintentar_con_backoff(invoke_fn, agent="Central")
            else:
                response = invoke_fn()
        finally:
            if provider in ("groq", "nvidia"):
                REMOTE_PACER.after_call(provider, "Central")
        try:
            parsed_response = json.loads(response.content)
            keys = sorted(parsed_response) if isinstance(parsed_response, dict) else []
            json_valid = True
        except (TypeError, json.JSONDecodeError):
            keys, json_valid = [], False
        logger.info(
            "CENTRAL_RESPONSE provider=%s model=%s chars=%s json_valid=%s keys=%s",
            provider,
            model,
            len(response.content),
            json_valid,
            keys,
        )
        audit["response"] = response.content
    return response.content


def formalizar_gaps_calidad(
    project_name: str,
    original_issue: Dict[str, Any],
    gaps_funcionales: List[Dict[str, Any]],
    llm_override: Any = None,
) -> List[Dict[str, Any]]:
    """
    Formaliza exclusivamente los gaps funcionales de confianza alta
    validados por el Agente de Calidad para una Historia de Usuario.

    No modifica retroactivamente la salida inicial del Agente Central:
    devuelve una lista independiente de requerimientos propuestos,
    pendientes de validación humana.
    """
    if not gaps_funcionales:
        return []

    entrada = {
        "historia_original": original_issue,
        "gaps_funcionales_validados": gaps_funcionales,
    }
    entrada_json_str = json.dumps(entrada, ensure_ascii=False)

    if llm_override is not None:
        llm = llm_override
    else:
        selection = obtener_llm_para_agente(
            "central",
            json_mode=True,
            num_predict=min(400 + len(gaps_funcionales) * 200, 1600),
            num_ctx=8192,
            temperature=0.1,
        )
        llm = selection.llm

    prompt_template = cargar_prompt("central_gaps_prompt.txt")
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        entrada_json_str=entrada_json_str,
    )

    with auditar_llamada_agente(
        "Central_Gaps",
        prompt_text=prompt_text,
        context_text=entrada_json_str,
        model_params={"json_mode": True},
    ) as audit:
        response = chain.invoke({
            "project_name": project_name,
            "entrada_json_str": entrada_json_str,
        })
        audit["response"] = response.content

    try:
        parsed = json.loads(response.content)
    except (TypeError, json.JSONDecodeError):
        logger.warning("CENTRAL_GAPS_RESPUESTA_NO_JSON issue=%r", original_issue.get("issue_iid"))
        return []

    propuestas_raw = parsed.get("requerimientos_propuestos") if isinstance(parsed, dict) else None

    return normalizar_requerimientos_propuestos_gap(propuestas_raw, gaps_funcionales)


class RespuestaCentralNoRecuperable(ValueError):
    """La respuesta requiere, como máximo, un reintento técnico localizado."""


def obtener_tamano_sublote_central(value: Any = None) -> int:
    raw = os.getenv("CENTRAL_BATCH_SIZE", "1") if value is None else value
    try:
        size = int(str(raw).strip())
        if size < 1:
            raise ValueError
        return size
    except (TypeError, ValueError):
        logger.warning("CENTRAL_BATCH_SIZE_INVALID usando_valor_predeterminado=1")
        return 1


def crear_sublotes_central(issues: List[Dict[str, Any]], size: int | None = None) -> List[List[Dict[str, Any]]]:
    batch_size = obtener_tamano_sublote_central(size)
    return [issues[index:index + batch_size] for index in range(0, len(issues), batch_size)]



def obtener_max_reintentos_tecnicos() -> int:
    raw = os.getenv("CENTRAL_MAX_TECHNICAL_RETRIES", "0")
    try:
        val = int(str(raw).strip())
        if val < 0:
            logger.warning("CENTRAL_MAX_TECHNICAL_RETRIES inválido. Usando 0.")
            return 0
        return val
    except (TypeError, ValueError):
        logger.warning("CENTRAL_MAX_TECHNICAL_RETRIES inválido. Usando 0.")
        return 0

def _contenido_central_utilizable(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    for field in ("actor", "funcionalidad", "objetivo"):
        val = item.get(field)
        if isinstance(val, str) and val.strip():
            return True
    for field in ("requerimientos", "restricciones", "criterios_aceptacion"):
        val = item.get(field)
        if isinstance(val, list) and val:
            for elem in val:
                if isinstance(elem, str) and elem.strip():
                    return True
                if isinstance(elem, dict) and elem:
                    return True
        elif isinstance(val, dict) and val:
            return True
        elif isinstance(val, str) and val.strip():
            return True
    return False

def _resolver_iid_candidato(candidate: dict, expected_iids: list) -> int | None:
    if not isinstance(candidate, dict):
        return None
    raw_iid = candidate.get("issue_iid")
    iid = normalizar_iid(raw_iid)
    if iid is None:
        if len(expected_iids) == 1:
            return expected_iids[0]
        return None
    if iid in expected_iids:
        return iid
    return None

def _crear_error_central(iid: int, history_id: str) -> dict:
    return {
        "issue_iid": iid,
        "historia_id": history_id,
        "status": "error",
        "motivo_sanitizado": "CENTRAL_LLM_OUTPUT_UNUSABLE",
        "campos_recuperados": [],
        "campos_ausentes": [],
        "evaluacion_posterior_posible": False
    }


def _normalizar_respuesta_central(raw: Any) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Acepta contrato normal o respuesta individual; no inventa historias."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise RespuestaCentralNoRecuperable("RESPUESTA_VACIA")
    recovered = False
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            data = json.loads(text)
            json_valid = True
        except json.JSONDecodeError as error:
            data = None
            decoder = json.JSONDecoder()
            for position, char in enumerate(text):
                if char != "{":
                    continue
                try:
                    candidate, _ = decoder.raw_decode(text[position:])
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict) and (
                    isinstance(candidate.get("resultados"), list)
                    or (candidate.get("issue_iid") is not None and candidate.get("historia_id"))
                ):
                    data, recovered = candidate, True
                    break
            if data is None:
                raise RespuestaCentralNoRecuperable("JSON_TRUNCADO_O_NO_RECUPERABLE") from error
            json_valid = False
    else:
        data, json_valid = raw, isinstance(raw, dict)
    if not isinstance(data, dict):
        raise RespuestaCentralNoRecuperable("JSON_RAIZ_NO_ES_OBJETO")
    for key in ("resultado", "result", "historia"):
        nested = data.get(key)
        if isinstance(nested, dict) and nested.get("issue_iid") is not None:
            data = nested
            recovered = True
            break
    direct = data.get("issue_iid") is not None
    if isinstance(data.get("resultados"), list):
        normalized = data
        category = "RESULTADOS"
    elif direct:
        normalized = {"agente": "central", "resultados": [data]}
        category = "RESPUESTA_INDIVIDUAL"
    else:
        normalized = {
            "agente": data.get("agente", "central"),
            "milestone": data.get("milestone", ""),
            "resultados": [data],
        }
        category = "JSON_SIN_RESULTADOS_CON_DATOS"
    return normalized, {
        "json_valid": json_valid, "json_recovered": recovered,
        "response_category": category,
    }


def obtener_proveedor_central() -> str:
    return os.getenv(
        "LLM_PROVIDER_CENTRAL",
        "ollama"
    ).strip().casefold()

def procesar_central_en_sublotes(
    project_name: str,
    issues: List[Dict[str, Any]],
    sprint_context: str,
    *,
    batch_size: int | None = None,
    invoke: Callable[[str, str, str], Any] = procesar_ticket,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa secuencialmente y consolida exclusivamente mediante issue_iid."""
    if invoke is procesar_ticket and obtener_proveedor_central() == "ollama":
        client_cache: Dict[tuple, Any] = {}

        def invoke_with_scoped_client(project: str, payload: str, context: str) -> Any:
            issue_count = len(json.loads(payload))
            num_predict = calcular_num_predict("Central_Init", issue_count)
            client = crear_cliente_ollama_central(client_cache, num_predict=num_predict)
            return procesar_ticket(
                project, payload, context,
                num_predict_override=num_predict, llm_override=client,
            )

        invoke = invoke_with_scoped_client
    initial_batches = crear_sublotes_central(issues, batch_size)
    original_order = [normalizar_iid(issue.get("issue_iid") or issue.get("id")) for issue in issues]
    expected_history_by_iid = {
        normalizar_iid(issue.get("issue_iid") or issue.get("id")): str(issue.get("historia_id") or "").strip()
        for issue in issues
    }
    results_by_iid: Dict[int, Dict[str, Any]] = {}
    failed: Dict[int, str] = {}
    records: List[Dict[str, Any]] = []
    milestone = ""
    sequence = 0

    def execute(group: List[Dict[str, Any]], split_level: int, repair: bool = False) -> None:
        nonlocal sequence, milestone
        sequence += 1
        sub_batch = sequence
        issue_ids = [normalizar_iid(issue.get("issue_iid") or issue.get("id")) for issue in group]
        num_predict = calcular_num_predict("Central_Init", len(group))
        started_at = datetime.now().isoformat(timespec="milliseconds")
        started = time.perf_counter()
        technical_retry = False
        parsed: Dict[str, Any] | None = None
        metadata = {"json_valid": False, "json_recovered": False, "response_category": ""}
        reason = ""
        status = "interrupted"
        received: List[int] = []
        registrar_evento_sublote_central(
            "central_sub_batch_start", sub_batch=sub_batch, split_level=split_level,
            issue_ids=issue_ids, call_type="selective_repair" if repair else "initial",
            num_predict=num_predict, started_at=started_at, status="started",
            received=list(results_by_iid), missing=issue_ids,
        )
        try:
            max_retries = obtener_max_reintentos_tecnicos()
            for attempt in range(max_retries + 1):
                call_type = "technical_retry" if attempt else ("selective_repair" if repair else "initial")
                call_started = time.perf_counter()
                registrar_evento_sublote_central(
                    "central_sub_batch_call_start", sub_batch=sub_batch,
                    split_level=split_level, issue_ids=issue_ids, call_type=call_type,
                    attempt=attempt + 1, num_predict=num_predict, status="started",
                    received=list(results_by_iid), missing=issue_ids,
                )
                try:
                    payload_group = [preparar_payload_central(item) for item in group]
                    raw = invoke(project_name, json.dumps(payload_group, ensure_ascii=False), sprint_context)
                    parsed, metadata = _normalizar_respuesta_central(raw)
                    call_received = []
                    for candidate in parsed.get("resultados", []):
                        iid = _resolver_iid_candidato(candidate, issue_ids)
                        if iid and iid not in call_received:
                            call_received.append(iid)
                    registrar_evento_sublote_central(
                        "central_sub_batch_call_end", sub_batch=sub_batch,
                        split_level=split_level, issue_ids=issue_ids, call_type=call_type,
                        attempt=attempt + 1, num_predict=num_predict,
                        elapsed_seconds=round(time.perf_counter() - call_started, 4),
                        status="success", received=call_received,
                        missing=[iid for iid in issue_ids if iid not in call_received],
                    )
                    break
                except RespuestaCentralNoRecuperable as error:
                    reason = str(error)
                    registrar_evento_sublote_central(
                        "central_sub_batch_error", sub_batch=sub_batch,
                        split_level=split_level, issue_ids=issue_ids, call_type=call_type,
                        attempt=attempt + 1, num_predict=num_predict,
                        elapsed_seconds=round(time.perf_counter() - call_started, 4),
                        status="failed", error_category="CENTRAL_RESPONSE_UNRECOVERABLE",
                        received=list(results_by_iid), missing=issue_ids,
                    )
                    if attempt < max_retries:
                        technical_retry = True
                        registrar_evento_grafo(
                            "agent_retry", "Central", reason=reason,
                            sub_batch=sub_batch, issue_ids=issue_ids,
                        )
                        continue
                except Exception as error:
                    category = "OLLAMA_CLIENT_CONFIGURATION_ERROR" if isinstance(error, FileNotFoundError) else type(error).__name__
                    registrar_evento_sublote_central(
                        "central_sub_batch_error", sub_batch=sub_batch,
                        split_level=split_level, issue_ids=issue_ids, call_type=call_type,
                        attempt=attempt + 1, num_predict=num_predict,
                        elapsed_seconds=round(time.perf_counter() - call_started, 4),
                        status="failed", error_category=category,
                        received=list(results_by_iid), missing=issue_ids,
                    )
                    status = "failed"
                    raise
            elapsed = round(time.perf_counter() - started, 4)
            if parsed is None:
                for iid in issue_ids:
                    results_by_iid[iid] = _crear_error_central(iid, expected_history_by_iid.get(iid, ""))
                    received.append(iid)
                
                status = "failed"
                record = {
                    "sub_batch": sub_batch, "split_level": split_level,
                    "issue_ids": issue_ids, "issue_count": len(group),
                    "num_predict": num_predict, "started_at": started_at,
                    "elapsed_seconds": elapsed, **metadata,
                    "expected": issue_ids, "received": issue_ids, "missing": [],
                    "technical_retry": technical_retry, "selective_repair": repair,
                    "selective_repair_requested": False,
                    "subdivision_applied": False, "reason": reason,
                    "status": "error",
                }
                records.append(record)
                registrar_sublote_central(record)
                for iid in issue_ids:
                    failed[iid] = reason
                return

            milestone = milestone or str(parsed.get("milestone") or "")
            for item in parsed.get("resultados", []):
                iid = _resolver_iid_candidato(item, issue_ids)
                if not iid or iid in received:
                    continue
                
                history_id_llm = str(item.get("historia_id") or "").strip()
                expected_history = expected_history_by_iid.get(iid, "")
                if history_id_llm and expected_history and history_id_llm != expected_history:
                    logger.warning(f"Contradicción de historia_id para {iid}: LLM envió {history_id_llm}, se esperaba {expected_history}")
                
                item["issue_iid"] = iid
                item["historia_id"] = expected_history
                
                if _contenido_central_utilizable(item):
                    source_validation = next(
                        (x.get("validacion_entrada", {}).get("estado") for x in group if normalizar_iid(x.get("issue_iid") or x.get("id")) == iid),
                        ""
                    )
                    if source_validation == "informacion_insuficiente":
                        item["status"] = "informacion_insuficiente"
                        item["evaluacion_posterior_posible"] = True
                    else:
                        item["status"] = "ok"
                else:
                    registrar_evento_grafo(
                        "central_llm_output_unusable", "Central_Init_Batch",
                        issue_iid=iid, historia_id=expected_history,
                        response_category=metadata.get("response_category", "UNKNOWN")
                    )
                    item = _crear_error_central(iid, expected_history)
                    
                results_by_iid[iid] = item
                received.append(iid)
                
            missing = [iid for iid in issue_ids if iid not in received]
            for iid in missing:
                results_by_iid[iid] = _crear_error_central(iid, expected_history_by_iid.get(iid, ""))
                received.append(iid)
            missing = []
            
            status = "success"
            record = {
                "sub_batch": sub_batch, "split_level": split_level,
                "issue_ids": issue_ids, "issue_count": len(group),
                "num_predict": num_predict, "started_at": started_at,
                "elapsed_seconds": elapsed, **metadata,
                "expected": issue_ids, "received": received, "missing": missing,
                "technical_retry": technical_retry, "selective_repair": repair,
                "selective_repair_requested": False,
                "subdivision_applied": False,
                "reason": "",
                "status": "success",
            }
            records.append(record)
            registrar_sublote_central(record)
            if repair:
                registrar_evento_grafo(
                    "selective_repair_completed", "Central_Init_Batch",
                    issue_ids=received,
                )
        finally:
            registrar_evento_sublote_central(
                "central_sub_batch_end", sub_batch=sub_batch, split_level=split_level,
                issue_ids=issue_ids, call_type="selective_repair" if repair else "initial",
                num_predict=num_predict, elapsed_seconds=round(time.perf_counter() - started, 4),
                status=status, received=received,
                missing=[iid for iid in issue_ids if iid not in received],
            )

    for group in initial_batches:
        execute(group, 0)

    ordered_results = [results_by_iid[iid] for iid in original_order if iid in results_by_iid]
    for item in ordered_results:
        normalizar_presentacion_requerimientos(item.get("requerimientos"))
    traceable = [iid for iid in original_order if iid in results_by_iid]
    successful = [iid for iid in traceable if results_by_iid[iid].get("status") == "ok"]
    insufficient = [iid for iid in traceable if results_by_iid[iid].get("status") == "informacion_insuficiente"]
    error = [iid for iid in traceable if results_by_iid[iid].get("status") == "error"]
    missing = [iid for iid in original_order if iid not in results_by_iid]

    summary = {
        "initial_sub_batches": len(initial_batches),
        "generated_sub_batches": len(records),
        "subdivision_generated_sub_batches": sum(record["split_level"] > 0 for record in records),
        "completed_sub_batches": sum(record["status"] == "success" for record in records),
        "failed_sub_batches": sum(record["status"] == "error" for record in records),
        "total_calls": sum(1 + int(record["technical_retry"]) for record in records),
        "selective_repairs": sum(bool(record["selective_repair"]) for record in records),
        "technical_retries": sum(bool(record["technical_retry"]) for record in records),
        "elapsed_seconds": round(sum(record["elapsed_seconds"] for record in records), 4),
        "expected_issue_ids": original_order,
        "traceable_issue_ids": traceable,
        "successful_issue_ids": successful,
        "insufficient_issue_ids": insufficient,
        "error_issue_ids": error,
        "missing_issue_ids": missing,
        "complete_issue_ids": traceable,
        "incomplete_issue_ids": missing,
    }
    failed_sub_batches = [
        int(record["sub_batch"]) for record in records
        if record.get("status") != "success"
    ]
    registrar_integridad_central(
        original_order, [iid for iid in original_order if iid in results_by_iid],
        failed_sub_batches=failed_sub_batches,
        selective_repairs_attempted=sum(bool(record.get("selective_repair")) for record in records),
        selective_repairs_completed=sum(
            bool(record.get("selective_repair")) and record.get("status") == "success"
            for record in records
        ),
    )
    registrar_evento_grafo("central_sub_batch_summary", "Central_Init", **summary)
    return {
        "agente": "central", "milestone": milestone,
        "resultados": ordered_results,
    }, {"records": records, "summary": summary, "failures": failed}
