from backend.integrations.whatsapp_sender import (
    send_whatsapp_message
)

result = send_whatsapp_message(
    "Hello! 👋\n\n"
    "This is my first ResearchRadar AI message "
    "sent directly from Python!"
)

print("WhatsApp message sent successfully!")
print(result)