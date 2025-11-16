from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import json
import requests
from datetime import datetime, timedelta
import uuid
from PIL import Image
import base64
from io import BytesIO
import speech_recognition as sr
import pyttsx3
import threading
import time
from twilio.rest import Client
import openai
import cv2
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

CORS(app)


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)


TWILIO_SID = 'AC81ee10673e12ba480c87340b01e7ef7e'
TWILIO_TOKEN = 'aa9048a297d2b4a3be420b25af486b3d'
TWILIO_PHONE = '+18723169149'


OPENAI_API_KEY = 'AIzaSyDaEyW-frAgMwhIkJTiRqY7W2W8-_6wHQU'


def init_db():
    conn = sqlite3.connect('agriculture.db')
    cursor = conn.cursor()
    

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            location TEXT NOT NULL,
            crop_type TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            voice_path TEXT,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            analysis_data TEXT NOT NULL,
            recommendations TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        location = data.get('location')
        crop_type = data.get('cropType')
        password = data.get('password')
        
        if not all([name, phone, location, crop_type, password]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        
        password_hash = generate_password_hash(password)
        
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
      
        cursor.execute('SELECT id FROM users WHERE phone = ?', (phone,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Phone number already registered'})
        
        cursor.execute('''
            INSERT INTO users (name, phone, location, crop_type, password_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, phone, location, crop_type, password_hash))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Registration successful'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username') 
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'success': False, 'message': 'Username and password required'})
        
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, location, crop_type, password_hash
            FROM users WHERE phone = ?
        ''', (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[5], password):
            user_data = {
                'id': user[0],
                'name': user[1],
                'phone': user[2],
                'location': user[3],
                'cropType': user[4]
            }
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login failed: {str(e)}'})


@app.route('/api/posts/create', methods=['POST'])
def create_post():
    try:
        user_id = request.form.get('userId', 'demo')
        content = request.form.get('description')
        
        if not content:
            return jsonify({'success': False, 'message': 'Content is required'})
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = f'uploads/{filename}'
        
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO posts (user_id, content, image_path)
            VALUES (?, ?, ?)
        ''', (user_id, content, image_path))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Post created successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Post creation failed: {str(e)}'})

@app.route('/api/posts/get-posts', methods=['GET'])
def get_posts():
    try:
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.id, p.content, p.image_path, p.likes, p.comments, p.created_at,
                   u.name, u.location
            FROM posts p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 20
        ''')
        
        posts_data = cursor.fetchall()
        conn.close()
        
        posts = []
        for post in posts_data:
            posts.append({
                'id': post[0],
                'content': post[1],
                'image': f'/static/{post[2]}' if post[2] else None,
                'likes': post[3],
                'comments': post[4],
                'timestamp': post[5],
                'user': {
                    'name': post[6],
                    'location': post[7]
                }
            })
        
        return jsonify({'success': True, 'posts': posts})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load posts: {str(e)}'})


@app.route('/api/sms/send-alert', methods=['POST'])
def send_weather_alert():
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('message')
        
     
        if TWILIO_SID != 'your_twilio_sid':
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            message = client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=phone
            )
            
            return jsonify({'success': True, 'message': 'Alert sent successfully'})
        else:
            
            print(f"SMS Alert to {phone}: {message}")
            return jsonify({'success': True, 'message': 'Alert logged (demo mode)'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send alert: {str(e)}'})

@app.route('/api/sms/send-recommendation', methods=['POST'])
def send_recommendation():
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('message')
        
   
        print(f"SMS Recommendation to {phone}: {message}")
        return jsonify({'success': True, 'message': 'Recommendation sent'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send recommendation: {str(e)}'})

@app.route('/api/sms/send-price-alert', methods=['POST'])
def send_price_alert():
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('message')
        

        print(f"Price Alert to {phone}: {message}")
        return jsonify({'success': True, 'message': 'Price alert sent'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send price alert: {str(e)}'})

@app.route('/api/analysis/image', methods=['POST'])
def analyze_image():
    try:
        data = request.json
        image_data = data.get('image')
        user_id = data.get('userId', 'demo')
        

        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(BytesIO(image_bytes))
        

        filename = f"analysis_{uuid.uuid4()}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)
        
    
        analysis_result = perform_crop_analysis(filepath)
        

        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analysis_results (user_id, image_path, analysis_data, recommendations)
            VALUES (?, ?, ?, ?)
        ''', (user_id, f'uploads/{filename}', json.dumps(analysis_result['analysis']), json.dumps(analysis_result['recommendations'])))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'analysis': analysis_result['analysis'],
            'recommendations': analysis_result['recommendations']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Analysis failed: {str(e)}'})

def perform_crop_analysis(image_path):
    """
    Mock crop analysis function - in real implementation, this would use
    computer vision and machine learning models
    """
    try:
  
        image = cv2.imread(image_path)
        
   
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        

        lower_green = np.array([40, 40, 40])
        upper_green = np.array([80, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        green_ratio = np.sum(mask > 0) / mask.size
        
      
        if green_ratio > 0.6:
            health_status = "Healthy"
            health_score = 85
        elif green_ratio > 0.3:
            health_status = "Moderate"
            health_score = 65
        else:
            health_status = "Poor"
            health_score = 35
        
        analysis = {
            'crop_health': health_status,
            'health_score': health_score,
            'green_coverage': round(green_ratio * 100, 2),
            'detected_issues': []
        }
        
        recommendations = [
            {
                'icon': 'fas fa-leaf',
                'title': 'Nutrient Management',
                'description': 'Apply balanced NPK fertilizer based on soil test results',
                'urgent': health_score < 50
            },
            {
                'icon': 'fas fa-water',
                'title': 'Irrigation',
                'description': 'Maintain optimal soil moisture levels through scheduled watering',
                'urgent': False
            }
        ]
        
        if health_score < 70:
            analysis['detected_issues'].append('Possible nutrient deficiency')
            recommendations.append({
                'icon': 'fas fa-exclamation-triangle',
                'title': 'Health Monitoring',
                'description': 'Monitor crop closely and consider expert consultation',
                'urgent': True
            })
        
        return {
            'analysis': analysis,
            'recommendations': recommendations
        }
        
    except Exception as e:
        print(f"Analysis error: {e}")
     
        return {
            'analysis': {
                'crop_health': 'Good',
                'health_score': 75,
                'green_coverage': 60,
                'detected_issues': []
            },
            'recommendations': [
                {
                    'icon': 'fas fa-leaf',
                    'title': 'General Care',
                    'description': 'Continue current farming practices',
                    'urgent': False
                }
            ]
        }

@app.route('/api/ai/process-voice', methods=['POST'])
def process_voice():
    try:
        data = request.json
        problem = data.get('problem')
        user_id = data.get('userId')
        

        ai_response = generate_ai_response(problem)
        
  
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_history (user_id, user_message, ai_response)
            VALUES (?, ?, ?)
        ''', (user_id, problem, ai_response))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'recommendation': ai_response,
            'sendSms': len(ai_response) < 160  
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Voice processing failed: {str(e)}'})

@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    try:
        data = request.json
        message = data.get('message')
        user_id = data.get('userId')
        context = data.get('context', {})
    
        ai_response = generate_ai_response(message, context)
      
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_history (user_id, user_message, ai_response)
            VALUES (?, ?, ?)
        ''', (user_id, message, ai_response))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'response': ai_response})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Chat failed: {str(e)}'})

def generate_ai_response(message, context=None):
    """
    Generate AI response for farming queries
    In production, this could integrate with OpenAI or other AI services
    """
    message_lower = message.lower()

    location = context.get('location', '') if context else ''
    crop_type = context.get('cropType', '') if context else ''
    

    if any(word in message_lower for word in ['weather', 'rain', 'temperature', 'climate']):
        responses = [
            f"Based on current weather patterns in {location}, I recommend monitoring rainfall closely. If heavy rain is expected, avoid pesticide application and ensure proper field drainage.",
            "Weather is crucial for farming decisions. Check the weather forecast section for detailed predictions. During monsoon, focus on disease prevention.",
            "Temperature changes affect crop growth significantly. For optimal results, plan your farming activities according to seasonal weather patterns."
        ]
        return responses[hash(message) % len(responses)]
    
    # Pest and disease queries
    elif any(word in message_lower for word in ['pest', 'insect', 'bug', 'disease', 'yellow', 'spots', 'fungus']):
        responses = [
            "For pest management, I recommend integrated pest management (IPM). Use neem oil as a natural pesticide, maintain field hygiene, and consider beneficial insects.",
            "Yellow spots on leaves often indicate fungal diseases or nutrient deficiency. Remove affected parts, improve air circulation, and avoid overhead watering.",
            "Early detection is key for pest control. Monitor your crops regularly, use pheromone traps, and apply organic pesticides when necessary."
        ]
        return responses[hash(message) % len(responses)]
    
    # Fertilizer and nutrition queries
    elif any(word in message_lower for word in ['fertilizer', 'nutrition', 'npk', 'organic', 'compost']):
        responses = [
            f"For {crop_type} crops, conduct a soil test first. Generally, apply nitrogen during vegetative growth, phosphorus during flowering, and potassium for overall plant health.",
            "Organic farming is beneficial for long-term soil health. Use compost, green manure, and bio-fertilizers. They improve soil structure and water retention.",
            "Balanced nutrition is essential. Avoid over-fertilization as it can lead to pest problems. Follow the 4R principle: Right source, Right rate, Right time, Right place."
        ]
        return responses[hash(message) % len(responses)]
    

    elif any(word in message_lower for word in ['water', 'irrigation', 'drought', 'watering']):
        responses = [
            "Water management is critical. Water early morning (5-7 AM) or late evening to minimize evaporation. Use drip irrigation for water efficiency.",
            "Check soil moisture before watering. Overwatering can lead to root rot and pest problems. Maintain proper drainage in fields.",
            "During water scarcity, focus on mulching to retain soil moisture, use drought-resistant varieties, and implement water harvesting techniques."
        ]
        return responses[hash(message) % len(responses)]

    elif any(word in message_lower for word in ['soil', 'ph', 'erosion', 'organic matter']):
        responses = [
            "Soil health is the foundation of successful farming. Test your soil pH regularly - most crops prefer 6.0-7.5 pH. Add lime if too acidic, sulfur if too alkaline.",
            "Improve soil organic matter by adding compost, crop residues, and practicing crop rotation. This enhances water retention and nutrient availability.",
            "Prevent soil erosion through contour farming, cover crops, and maintaining vegetation buffers. Healthy soil supports better crop yields."
        ]
        return responses[hash(message) % len(responses)]
    

    elif any(word in message_lower for word in ['market', 'price', 'sell', 'profit', 'economics']):
        responses = [
            "Market timing is crucial for profitability. Monitor price trends, consider value addition through processing, and explore direct marketing to consumers.",
            "Diversify your crops to reduce market risks. Grow high-value crops like vegetables and herbs alongside staple crops for better returns.",
            "Keep production records to calculate costs accurately. Focus on quality produce as it fetches better prices in the market."
        ]
        return responses[hash(message) % len(responses)]
    
    elif any(word in message_lower for word in ['seed', 'planting', 'sowing', 'germination', 'variety']):
        responses = [
            "Choose certified seeds from reputable sources. Consider climate-resilient varieties that suit your local conditions and market demands.",
            "Proper seed treatment prevents diseases and improves germination. Soak seeds in appropriate solutions before planting.",
            "Timing of sowing is critical. Plant according to seasonal calendar and local weather patterns for optimal results."
        ]
        return responses[hash(message) % len(responses)]
    
    elif any(word in message_lower for word in ['harvest', 'storage', 'drying', 'post-harvest']):
        responses = [
            "Harvest at the right maturity stage for best quality and storability. Use proper harvesting tools to minimize damage.",
            "Post-harvest handling is crucial for reducing losses. Dry produce properly, use appropriate storage containers.",
            "Value addition through processing can significantly increase income. Consider making products like pickles, dried vegetables."
        ]
        return responses[hash(message) % len(responses)]
    
    
    else:
        responses = [
            f"As a farmer in {location}, focus on sustainable practices that improve both productivity and profitability. I'm here to help with specific questions about your {crop_type} crops.",
            "Successful farming requires continuous learning and adaptation. Keep records of your farming activities, monitor crop performance, and adjust practices accordingly.",
            "Technology can greatly benefit modern farming. Use weather apps, soil testing, and precision agriculture techniques.",
            "I'm your AI agriculture assistant. You can ask me about weather, pests, fertilizers, irrigation, soil health, market prices."
        ]
        return responses[hash(message) % len(responses)]


@app.route('/api/weather/current', methods=['GET'])
def get_current_weather():
    try:
        location = request.args.get('location', 'Delhi')
        
   
        weather_data = {
            'temperature': np.random.randint(20, 40),
            'humidity': np.random.randint(40, 80),
            'condition': np.random.choice(['Sunny', 'Cloudy', 'Rainy', 'Partly Cloudy']),
            'wind_speed': np.random.randint(5, 25),
            'rainfall_prediction': np.random.choice([0, 5, 15, 30]),
            'alerts': []
        }
        
   
        if weather_data['rainfall_prediction'] > 20:
            weather_data['alerts'].append({
                'type': 'rain',
                'message': 'Heavy rain expected in next 24 hours - avoid pesticide application',
                'severity': 'high'
            })
        
        if weather_data['temperature'] > 35:
            weather_data['alerts'].append({
                'type': 'heat',
                'message': 'High temperature alert - increase irrigation frequency',
                'severity': 'medium'
            })
        
        return jsonify({'success': True, 'weather': weather_data})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Weather data failed: {str(e)}'})


@app.route('/api/market/prices', methods=['GET'])
def get_market_prices():
    try:
        crop = request.args.get('crop', 'wheat')
        location = request.args.get('location', 'Delhi')
     
     
        base_prices = {
            'wheat': 2200,
            'rice': 1900,
            'corn': 1600,
            'vegetables': 3000,
            'fruits': 4000
        }
        
  
  
        base_price = base_prices.get(crop, 2000)
        current_price = base_price + np.random.randint(-200, 300)
        
        price_data = {
            'crop': crop,
            'location': location,
            'current_price': current_price,
            'previous_price': base_price,
            'change_percent': round(((current_price - base_price) / base_price) * 100, 2),
            'trend': 'up' if current_price > base_price else 'down',
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'price_data': price_data})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Market data failed: {str(e)}'})

@app.route('/api/satellite/analysis', methods=['POST'])
def satellite_analysis():
    try:
        data = request.json
        coordinates = data.get('coordinates')
        user_id = data.get('userId')

        satellite_data = {
            'ndvi': round(np.random.uniform(0.3, 0.8), 3),  # Vegetation index
            'soil_moisture': round(np.random.uniform(20, 80), 1),
            'temperature': round(np.random.uniform(20, 40), 1),
            'crop_stress_level': np.random.choice(['Low', 'Medium', 'High']),
            'recommended_actions': []
        }
        

        if satellite_data['ndvi'] < 0.5:
            satellite_data['recommended_actions'].append('Consider fertilizer application - vegetation index is low')
        
        if satellite_data['soil_moisture'] < 30:
            satellite_data['recommended_actions'].append('Irrigation required - soil moisture is low')
        
        if satellite_data['crop_stress_level'] == 'High':
            satellite_data['recommended_actions'].append('Immediate attention required - high crop stress detected')
        
        return jsonify({'success': True, 'satellite_data': satellite_data})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Satellite analysis failed: {str(e)}'})


@app.route('/api/voice/process-audio', methods=['POST'])
def process_voice_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'message': 'No audio file provided'})
        
        audio_file = request.files['audio']
        

        filename = secure_filename(f"voice_{uuid.uuid4()}.wav")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(filepath)
        

        r = sr.Recognizer()
        with sr.AudioFile(filepath) as source:
            audio_data = r.record(source)
            
        try:
            text = r.recognize_google(audio_data, language='hi-IN')
        except:
            try:
                text = r.recognize_google(audio_data, language='en-IN')
            except:
                text = "Could not understand audio"
        
   
        os.remove(filepath)
        
    
        ai_response = generate_ai_response(text)
        
        return jsonify({
            'success': True, 
            'transcribed_text': text,
            'ai_response': ai_response
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Voice processing failed: {str(e)}'})


@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    try:
        conn = sqlite3.connect('agriculture.db')
        cursor = conn.cursor()
        
  
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM posts')
        total_posts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM chat_history')
        total_chats = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analysis_results')
        total_analyses = cursor.fetchone()[0]
        
        conn.close()
        
        stats = {
            'total_users': total_users,
            'total_posts': total_posts,
            'total_chats': total_chats,
            'total_analyses': total_analyses,
            'active_today': np.random.randint(5, 25),  
            'alerts_sent': np.random.randint(10, 50)   
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Stats failed: {str(e)}'})


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500


def weather_monitoring_task():
    """Background task to monitor weather and send alerts"""
    while True:
        try:
            conn = sqlite3.connect('agriculture.db')
            cursor = conn.cursor()
            
          
            cursor.execute('SELECT id, phone, location FROM users')
            users = cursor.fetchall()
            
            for user in users:
                if np.random.random() < 0.1:  
                    alert_message = "Weather Alert: Heavy rain expected tomorrow. Avoid pesticide application and ensure proper drainage."
                    
                    print(f"Weather Alert sent to {user[1]}: {alert_message}")
                    
 
                    cursor.execute('''
                        INSERT INTO weather_alerts (user_id, alert_type, message)
                        VALUES (?, ?, ?)
                    ''', (user[0], 'weather', alert_message))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Weather monitoring error: {e}")
        

        time.sleep(3600)


if __name__ == '__main__':
    weather_thread = threading.Thread(target=weather_monitoring_task, daemon=True)
    weather_thread.start()
    
    print("🌱 AgriAdvisor Backend Server Starting...")
    print("📱 Features: SMS Alerts, Voice Processing, Satellite Analysis, AI Chat")
    print("🚀 Server running on http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)