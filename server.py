from flask import Flask, request, jsonify
import json
import os
from datetime import datetime
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ملف قاعدة البيانات
DB_FILE = 'licenses.json'
API_SECRET = os.environ.get('API_SECRET', 'change_me_in_production')

logger.info(f"Server starting with API_SECRET configured: {bool(API_SECRET)}")

def load_licenses():
    """تحميل التراخيص من الملف"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} licenses from database")
                return data
    except Exception as e:
        logger.error(f"Error loading licenses: {e}")
    return {}

def save_licenses(data):
    """حفظ التراخيص في الملف"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(data)} licenses to database")
        return True
    except Exception as e:
        logger.error(f"Error saving licenses: {e}")
        return False

@app.route('/')
def home():
    """الصفحة الرئيسية - للتأكد أن السيرفر شغال"""
    logger.info("Home endpoint accessed")
    return jsonify({
        'status': 'running',
        'message': 'POS License Server is running',
        'version': '1.0',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/health')
def health():
    """فحص صحة السيرفر - مطلوب من Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/ping')
def ping():
    """نقطة اختبار بسيطة"""
    return 'pong', 200

@app.route('/verify', methods=['POST'])
def verify_license():
    """التحقق من صلاحية الترخيص"""
    try:
        data = request.get_json()
        if not data:
            logger.warning("Verify request with no data")
            return jsonify({'valid': False, 'error': 'No data provided'}), 400
        
        license_key = data.get('license_key')
        if not license_key:
            logger.warning("Verify request with no license key")
            return jsonify({'valid': False, 'error': 'No license key'}), 400
        
        licenses = load_licenses()
        
        if license_key in licenses:
            license_info = licenses[license_key]
            
            try:
                expiry = datetime.strptime(license_info['expiry_date'], '%Y-%m-%d')
            except Exception as e:
                logger.error(f"Invalid date format: {e}")
                return jsonify({'valid': False, 'error': 'Invalid date format'}), 400
            
            if datetime.now() <= expiry and license_info.get('status') == 'active':
                # تحديث آخر استخدام
                licenses[license_key]['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_licenses(licenses)
                
                logger.info(f"License verified successfully: {license_key[:8]}...")
                return jsonify({
                    'valid': True,
                    'customer_name': license_info.get('customer_name', 'Unknown'),
                    'expiry_date': license_info['expiry_date']
                }), 200
        
        logger.warning(f"Invalid license key attempted: {license_key[:8] if license_key else 'None'}...")
        return jsonify({'valid': False}), 200
    
    except Exception as e:
        logger.error(f"Error in verify: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 500

@app.route('/add_license', methods=['POST'])
def add_license():
    """إضافة ترخيص جديد"""
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Add license request with no data")
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        if data.get('api_secret') != API_SECRET:
            logger.warning("Unauthorized add license attempt")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        required_fields = ['license_key', 'customer_name', 'expiry_date']
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing field in add license: {field}")
                return jsonify({'success': False, 'error': f'Missing {field}'}), 400
        
        licenses = load_licenses()
        licenses[data['license_key']] = {
            'customer_name': data['customer_name'],
            'expiry_date': data['expiry_date'],
            'status': 'active',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_used': None
        }
        
        if save_licenses(licenses):
            logger.info(f"License added: {data['customer_name']}")
            return jsonify({'success': True}), 200
        else:
            logger.error("Failed to save license")
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
    
    except Exception as e:
        logger.error(f"Error in add_license: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_license', methods=['POST'])
def update_license():
    """تحديث ترخيص موجود"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        if data.get('api_secret') != API_SECRET:
            logger.warning("Unauthorized update license attempt")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        licenses = load_licenses()
        
        if data['license_key'] in licenses:
            licenses[data['license_key']].update({
                'customer_name': data.get('customer_name', licenses[data['license_key']]['customer_name']),
                'expiry_date': data.get('expiry_date', licenses[data['license_key']]['expiry_date']),
                'status': data.get('status', licenses[data['license_key']]['status'])
            })
            
            if save_licenses(licenses):
                logger.info(f"License updated: {data['license_key'][:8]}...")
                return jsonify({'success': True}), 200
            else:
                return jsonify({'success': False, 'error': 'Failed to save'}), 500
        
        logger.warning(f"License not found for update: {data.get('license_key', 'None')[:8]}...")
        return jsonify({'success': False, 'error': 'License not found'}), 404
    
    except Exception as e:
        logger.error(f"Error in update_license: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_licenses', methods=['POST'])
def get_licenses():
    """الحصول على جميع التراخيص"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        if data.get('api_secret') != API_SECRET:
            logger.warning("Unauthorized get licenses attempt")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        licenses = load_licenses()
        logger.info(f"Get licenses request - returning {len(licenses)} licenses")
        return jsonify(licenses), 200
    
    except Exception as e:
        logger.error(f"Error in get_licenses: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)