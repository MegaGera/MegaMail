import boto3
from botocore.exceptions import ClientError
import os
import base64
import mjml

# --- CONFIGURATION ---
SENDER = "no-reply@megagera.com"  # Must be verified in SES
RECIPIENT = "gera1397@gmail.com"          # Can be any email if SES is out of sandbox
# RECIPIENT = "carloscamarerodg@gmail.com"          # Can be any email if SES is out of sandbox
AWS_REGION = "eu-west-1"                     # Change to your SES region
SUBJECT = "Thank you for your feedback! - MegaGoal"
MJML_TEMPLATE_PATH = "templates/feedback_email_template.mjml"
ASSETS_DIR = "assets"

# --- LOAD AND ENCODE IMAGES ---
def load_image_as_base64(image_path):
    """Load an image file and convert it to base64 data URI."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_file = os.path.join(script_dir, image_path)
    try:
        with open(image_file, 'rb') as f:
            image_data = f.read()
            # Determine MIME type based on file extension
            ext = os.path.splitext(image_path)[1].lower()
            mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
            mime_type = mime_types.get(ext, 'image/png')
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f"data:{mime_type};base64,{base64_data}"
    except FileNotFoundError:
        raise FileNotFoundError(f"Image not found at: {image_file}")
    except Exception as e:
        raise Exception(f"Error reading image: {e}")

# --- LOAD AND COMPILE MJML TEMPLATE ---
def load_mjml_template(template_path):
    """Load MJML email template from file, compile to HTML, and inject images."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(script_dir, template_path)
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            mjml_content = f.read()
        
        # Load and inject images before compilation
        megagoal_logo = load_image_as_base64(os.path.join(ASSETS_DIR, "MegaGoal.png"))
        megagoal_full_logo = load_image_as_base64(os.path.join(ASSETS_DIR, "MegaGoal_full.png"))
        
        # Replace placeholders
        mjml_content = mjml_content.replace("{{MEGAGOAL_LOGO}}", megagoal_logo)
        mjml_content = mjml_content.replace("{{MEGAGOAL_FULL_LOGO}}", megagoal_full_logo)
        
        # Compile MJML to HTML
        html_output = mjml.mjml_to_html(mjml_content)
        if html_output.get('errors'):
            raise Exception(f"MJML compilation errors: {html_output['errors']}")
        
        return html_output['html']
    except FileNotFoundError:
        raise FileNotFoundError(f"MJML template not found at: {template_file}")
    except Exception as e:
        raise Exception(f"Error processing MJML template: {e}")

BODY_HTML = load_mjml_template(MJML_TEMPLATE_PATH)

# Plain text version (fallback for email clients that don't support HTML)
BODY_TEXT = """Thank you for your feedback!

We truly appreciate you taking the time to share your thoughts with us. Your feedback is incredibly valuable and helps us improve.

We're reviewing your comments and will work on implementing improvements based on your suggestions.

Visit us at https://megagoal.megagera.com to continue your journey with MegaGoal.

---
This is an automated email. Please do not reply directly to this message.
"""

# --- SES CLIENT ---
ses_client = boto3.client('ses', region_name=AWS_REGION)

# --- EMAIL SENDING ---
def send_email():
    try:
        response = ses_client.send_email(
            Source=SENDER,
            Destination={
                'ToAddresses': [RECIPIENT],
            },
            Message={
                'Subject': {'Data': SUBJECT},
                'Body': {
                    'Html': {'Data': BODY_HTML},
                    'Text': {'Data': BODY_TEXT}
                },
            },
        )
        print(f"Email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        print(f"Failed to send email: {e.response['Error']['Message']}")

if __name__ == "__main__":
    send_email() 