from flask import Flask, request, jsonify
from flask_cors import CORS  # <-- Añade esta línea
from app.db import get_connection, return_connection
from app.models import Cliente, Evaluacion
import requests
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)  # <-- Añade esta línea para habilitar CORS para todos los dominios

# Mock de servicio externo (simula respuesta crediticia)
def mock_servicio_externo(dni):
    return {
        "dni": dni,
        "score": random.randint(300, 850),  # Simula FICO Score (300-850)
        "deuda_total": random.randint(1000, 50000),
        "historico": random.choice(["excelente", "bueno", "regular", "malo"])
    }

# Mock de modelo ML (simula evaluación)
def mock_modelo_ml(data):
    aprobado = (data['ingresos_mensuales'] / max(1, data['deuda_actual'])) > 0.5
    return {
        "aprobado": aprobado,
        "score": round(random.uniform(0.5, 1.0), 2),  # Score entre 0.5 y 1.0
        "razon": "Relación ingresos/deuda favorable" if aprobado else "Deuda muy alta"
    }

@app.route('/evaluar', methods=['POST'])
def evaluar_credito():
    # 1. Validar datos del formulario
    try:
        form_data = request.json
        cliente_data = Cliente(**{
            "dni": form_data['dni'],
            "nombre": form_data['nombre'],
            "email": form_data['email'],
            "telefono": form_data.get('telefono'),
            "direccion": form_data.get('direccion')
        }).dict()
        
        evaluacion_data = Evaluacion(**{
            "dni_cliente": form_data['dni'],
            "ingresos_mensuales": float(form_data['ingresos_mensuales']),
            "deuda_actual": float(form_data.get('deuda_actual', 0)),
            "historial_crediticio": form_data['historial_crediticio']
        }).dict()
    except Exception as e:
        return jsonify({"error": f"Datos inválidos: {str(e)}"}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 2. Guardar en PostgreSQL
            # Insertar/actualizar cliente
            cur.execute("""
                INSERT INTO clientes (dni, nombre, email, telefono, direccion)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (dni) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    email = EXCLUDED.email,
                    telefono = EXCLUDED.telefono,
                    direccion = EXCLUDED.direccion
                RETURNING id
            """, (
                cliente_data['dni'],
                cliente_data['nombre'],
                cliente_data['email'],
                cliente_data['telefono'],
                cliente_data['direccion']
            ))
            cliente_id = cur.fetchone()[0]

            # Insertar evaluación inicial
            cur.execute("""
                INSERT INTO evaluaciones (
                    cliente_id, 
                    ingresos_mensuales, 
                    deuda_actual, 
                    historial_crediticio
                ) VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                cliente_id,
                evaluacion_data['ingresos_mensuales'],
                evaluacion_data['deuda_actual'],
                evaluacion_data['historial_crediticio']
            ))
            evaluacion_id = cur.fetchone()[0]
            conn.commit()

            # 3. Mock servicio externo
            servicio_externo = mock_servicio_externo(cliente_data['dni'])
            
            # Actualizar evaluación con datos externos
            cur.execute("""
                UPDATE evaluaciones 
                SET 
                    score_credito_externo = %s,
                    deuda_total_externa = %s,
                    historico_externo = %s
                WHERE id = %s
            """, (
                servicio_externo['score'],
                servicio_externo['deuda_total'],
                servicio_externo['historico'],
                evaluacion_id
            ))
            conn.commit()

            # 4. Mock modelo ML
            data_ml = {
                'ingresos_mensuales': evaluacion_data['ingresos_mensuales'],
                'deuda_actual': evaluacion_data['deuda_actual'],
                'score_externo': servicio_externo['score'],
                'historial': evaluacion_data['historial_crediticio']
            }
            resultado_ml = mock_modelo_ml(data_ml)

            # Actualizar evaluación con resultado ML
            cur.execute("""
                UPDATE evaluaciones 
                SET 
                    resultado_ml = %s,
                    score_ml = %s,
                    razon_ml = %s,
                    fecha_actualizacion = NOW()
                WHERE id = %s
                RETURNING *
            """, (
                resultado_ml['aprobado'],
                resultado_ml['score'],
                resultado_ml['razon'],
                evaluacion_id
            ))
            evaluacion_final = cur.fetchone()
            conn.commit()

            # 5. Respuesta al frontend
            return jsonify({
                "evaluacion_id": evaluacion_id,
                "aprobado": resultado_ml['aprobado'],
                "score": resultado_ml['score'],
                "razon": resultado_ml['razon'],
                "datos_externos": servicio_externo
            }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Error en BD: {str(e)}"}), 500
    finally:
        return_connection(conn)

@app.route('/evaluaciones/<dni>', methods=['GET'])
def obtener_evaluaciones(dni):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    e.id, e.ingresos_mensuales, e.deuda_actual,
                    e.score_credito_externo, e.resultado_ml, e.score_ml,
                    e.fecha_evaluacion
                FROM evaluaciones e
                JOIN clientes c ON e.cliente_id = c.id
                WHERE c.dni = %s
                ORDER BY e.fecha_evaluacion DESC
            """, (dni,))
            
            evaluaciones = []
            for row in cur.fetchall():
                evaluaciones.append({
                    "id": row[0],
                    "ingresos": row[1],
                    "deuda": row[2],
                    "score_externo": row[3],
                    "aprobado": row[4],
                    "score_ml": row[5],
                    "fecha": row[6].isoformat()
                })
            
            return jsonify({"evaluaciones": evaluaciones}), 200
    finally:
        return_connection(conn)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)