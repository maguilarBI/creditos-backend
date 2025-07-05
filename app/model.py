from pydantic import BaseModel

class Cliente(BaseModel):
    dni: str
    nombre: str
    email: str
    telefono: str = None
    direccion: str = None

class Evaluacion(BaseModel):
    dni_cliente: str
    ingresos_mensuales: float
    deuda_actual: float = 0
    historial_crediticio: str  # "bueno", "regular", "malo"