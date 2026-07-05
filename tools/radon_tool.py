import subprocess
import os

def run_radon(target_path: str) -> str:
    """
    Ejecuta Radon para obtener métricas de calidad de código (complejidad ciclomática).
    """
    if not os.path.exists(target_path):
        return f"Error: La ruta {target_path} no existe."
    
    try:
        # Ejecutamos radon cc para complejidad ciclomática
        result = subprocess.run(
            ['radon', 'cc', target_path, '-a'],
            capture_output=True,
            text=True,
            check=False
        )
        
        output = result.stdout
        if not output.strip():
            output = "No se encontraron problemas de complejidad o el directorio está vacío."
        
        return f"Resultados de Radon (Calidad):\n{output}"
        
    except Exception as e:
        return f"Error al ejecutar radon: {str(e)}"
