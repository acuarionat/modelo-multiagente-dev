import subprocess
import os

def ejecutar_semgrep(target_path: str) -> str:
    """
    Ejecuta Semgrep para análisis de seguridad estático (SAST).
    Nota: Las reglas específicas se establecerán más adelante.
    """
    if not os.path.exists(target_path):
        return f"Error: La ruta {target_path} no existe."
    
    try:
        # Por ahora usamos reglas automáticas/básicas como placeholder.
        # Las reglas específicas se ajustarán en el futuro.
        result = subprocess.run(
            ['semgrep', '--config', 'auto', target_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        output = result.stdout
        error_output = result.stderr
        
        # Semgrep a veces reporta hallazgos en stdout y logs en stderr
        if "No findings" in output or not output.strip():
            if error_output:
                return f"Semgrep Output/Log:\n{error_output}"
            return "Resultados de Semgrep (Seguridad): No se encontraron vulnerabilidades."
            
        return f"Resultados de Semgrep (Seguridad):\n{output}"
        
    except Exception as e:
        return f"Error al ejecutar semgrep: {str(e)}"
