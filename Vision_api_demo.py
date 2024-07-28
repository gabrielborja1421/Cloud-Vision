from flask import Flask, request, jsonify
import os
import io
from google.cloud import vision
import pika
import json
import requests

# Configurar la variable de entorno con la ruta al archivo de credenciales
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'ServiceAccountToken.json'

app = Flask(__name__)

# Configuración de RabbitMQ
RABBITMQ_URL = 'amqps://b-d8bf4680-1797-47c9-9046-a985d952d538.mq.us-east-1.amazonaws.com:5671'
RABBITMQ_USER = 'Entrenat'  # Reemplaza con tu usuario de RabbitMQ
RABBITMQ_PASSWORD = '@Recursos1421'  # Reemplaza con tu contraseña de RabbitMQ

def publish_message_to_queue(message):
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(RABBITMQ_URL, 5671, '/', credentials, ssl_options=pika.SSLOptions())
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='image_queue', durable=True)
    channel.basic_publish(
        exchange='',
        routing_key='image_queue',
        body=message,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ))
    connection.close()

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'pong'}), 200

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files or 'user_id' not in request.form:
        return jsonify({'error': 'No image or user_id provided'}), 400

    image_file = request.files['image']
    user_id = request.form['user_id']
    content = image_file.read()

    # Crear el cliente de la API de Vision
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)

    # Llamar a la API de Vision para la detección de contenido seguro
    response = client.safe_search_detection(image=image)
    safe_search = response.safe_search_annotation

    # Verificar si hay errores en la respuesta
    if response.error.message:
        return jsonify({'error': response.error.message}), 500

    # Crear el resultado como un diccionario
    inappropriate_content = (
        safe_search.adult >= vision.Likelihood.VERY_LIKELY or
        safe_search.medical >= vision.Likelihood.VERY_LIKELY or
        safe_search.violence >= vision.Likelihood.VERY_LIKELY
    )

    if inappropriate_content:
        return jsonify({'explicit': True, 'message': 'Image contains inappropriate content'}), 400

    # Si la imagen es apropiada, subirla a un servicio de almacenamiento (por ejemplo, Cloudinary)
    try:
        upload_response = requests.post(
            'http://3.218.77.178:8000/image/', 
            files={'file': content}, 
            data={'upload_preset': 'your-upload-preset'}
        )
        upload_result = upload_response.json()

        image_url = upload_result['secure_url']
        image_public_id = upload_result['public_id']
        image_extension = upload_result['format']

        # Preparar la respuesta y el mensaje de RabbitMQ
        response_data = {
            'USERID': user_id,
            'name': image_file.filename,
            'extension': image_extension,
            'link': image_url,
            'user_id': user_id,
            'publicId': image_public_id
        }

        publish_message_to_queue(json.dumps(response_data))

        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image/<user_id>', methods=['PUT'])
def update_image(user_id):
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    image_file = request.files['image']
    content = image_file.read()

    # Crear el cliente de la API de Vision
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)

    # Llamar a la API de Vision para la detección de contenido seguro
    response = client.safe_search_detection(image=image)
    safe_search = response.safe_search_annotation

    # Verificar si hay errores en la respuesta
    if response.error.message:
        return jsonify({'error': response.error.message}), 500

    # Crear el resultado como un diccionario
    inappropriate_content = (
        safe_search.adult >= vision.Likelihood.VERY_LIKELY or
        safe_search.medical >= vision.Likelihood.VERY_LIKELY or
        safe_search.violence >= vision.Likelihood.VERY_LIKELY
    )

    if inappropriate_content:
        return jsonify({'explicit': True, 'message': 'Image contains inappropriate content'}), 400

    # Si la imagen es apropiada, subirla a un servicio de almacenamiento (por ejemplo, Cloudinary)
    try:
        upload_response = requests.post(
            'http://3.218.77.178:8000/image/upload', 
            files={'file': content}, 
            data={'upload_preset': 'your-upload-preset'}
        )
        upload_result = upload_response.json()

        image_url = upload_result['secure_url']
        image_public_id = upload_result['public_id']
        image_extension = upload_result['format']

        # Preparar la respuesta y el mensaje de RabbitMQ
        response_data = {
            'USERID': user_id,
            'name': image_file.filename,
            'extension': image_extension,
            'link': image_url,
            'user_id': user_id,
            'publicId': image_public_id
        }

        publish_message_to_queue(json.dumps(response_data))

        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
