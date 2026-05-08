import os
import requests
from flask import Flask, request
from address_printer import parse_address_block, create_address_document, BLOCKS_PER_PAGE

app = Flask(__name__)

# ==========================================
# 🔑 SECURITY UPDATE FOR RENDER
# ==========================================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "cream_bot_123")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
# ==========================================

# In-memory store for active sessions
sessions = {}

def send_whatsapp_message(to_number, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=data)

def send_whatsapp_document(to_number, document_path, filename):
    # Step 1: Upload document to Meta's servers
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    
    mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    files = {
        'file': (filename, open(document_path, 'rb'), mime_type),
        'type': (None, mime_type),
        'messaging_product': (None, 'whatsapp')
    }
    
    upload_res = requests.post(url, headers=headers, files=files)
    media_id = upload_res.json().get('id')
    
    if not media_id:
        send_whatsapp_message(to_number, "⚠️ Error uploading document to WhatsApp.")
        return False
        
    # Step 2: Send document back to your phone
    msg_url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    msg_headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename
        }
    }
    requests.post(msg_url, headers=msg_headers, json=data)
    return True

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook with Meta (This connects Meta to our Bot)"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Forbidden', 403
    return 'Bad Request', 400

@app.route('/webhook', methods=['POST'])
def webhook_event():
    """Handle incoming WhatsApp messages from your iPhone"""
    body = request.get_json()
    
    if body.get('object'):
        if body.get('entry') and body['entry'][0].get('changes') and body['entry'][0]['changes'][0].get('value').get('messages'):
            message_data = body['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_data['from']
            
            if 'text' in message_data:
                msg_text = message_data['text']['body'].strip()
                handle_incoming_message(phone_number, msg_text)
                
        return 'EVENT_RECEIVED', 200
    else:
        return 'Not Found', 404

def handle_incoming_message(phone_number, msg_text):
    lower_msg = msg_text.lower()
    
    if phone_number not in sessions:
        sessions[phone_number] = {'biller_id': '1260357626', 'addresses': [], 'is_recording': False, 'is_choosing_biller': False}
        
    session = sessions[phone_number]
    
    if lower_msg == 'start':
        session['addresses'] = []
        session['is_recording'] = False
        session['is_choosing_biller'] = True
        
        menu = (
            "Started new batch!\n\n"
            "Please choose a Biller ID by replying with 1, 2, or 3:\n"
            "1 - 1260357626\n"
            "2 - 1264602129\n"
            "3 - 1624036027"
        )
        send_whatsapp_message(phone_number, menu)
        return
        
    if session['is_choosing_biller']:
        options = {'1': '1260357626', '2': '1264602129', '3': '1624036027'}
        if msg_text in options:
            session['biller_id'] = options[msg_text]
            session['is_choosing_biller'] = False
            session['is_recording'] = True
            send_whatsapp_message(phone_number, f"Biller ID set to {options[msg_text]}.\n\nForward your addresses now. (I will stay completely silent so your chat stays clean). Type 'stop' when done.")
        else:
            send_whatsapp_message(phone_number, "Invalid option. Please reply with 1, 2, or 3.")
        return
        
    if lower_msg == 'stop':
        if not session['is_recording']:
            send_whatsapp_message(phone_number, "⚠️ You are not recording a batch. Type 'start' to begin.")
            return
            
        if not session['addresses']:
            send_whatsapp_message(phone_number, "⚠️ No addresses were sent. Batch canceled.")
            session['is_recording'] = False
            return
            
        send_whatsapp_message(phone_number, f"🔄 Generating label document with {len(session['addresses'])} addresses...")
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        docx_filename = f"addresses_{timestamp}.docx"
        
        os.makedirs("output", exist_ok=True)
        docx_path = os.path.join("output", docx_filename)
        
        doc = create_address_document(session['addresses'], session['biller_id'], "prepaidtemplate.docx")
        doc.save(docx_path)
        
        success = send_whatsapp_document(phone_number, docx_path, docx_filename)
        
        session['is_recording'] = False
        session['addresses'] = []
        return
        
    if lower_msg == 'list':
        if not session['addresses']:
            send_whatsapp_message(phone_number, "📋 List is empty.")
        else:
            list_text = f"📋 Current List ({len(session['addresses'])}):\n\n"
            for i, addr in enumerate(session['addresses'], 1):
                list_text += f"{i}. {addr['name'] or 'No Name'} - {addr['pincode'] or 'No Pin'}\n"
            send_whatsapp_message(phone_number, list_text)
        return
        
    if lower_msg == 'undo':
        if session['addresses']:
            removed = session['addresses'].pop()
            send_whatsapp_message(phone_number, f"↩️ Removed: {removed['name']}")
        else:
            send_whatsapp_message(phone_number, "⚠️ Nothing to undo.")
        return

    # If we are recording, parse as address
    if session['is_recording']:
        parsed = parse_address_block(msg_text)
        session['addresses'].append(parsed)
        # SILENT! We don't send any confirmation message here anymore.
    else:
        # Ignore random messages when not recording
        pass

if __name__ == '__main__':
    app.run(port=5000, debug=True)
