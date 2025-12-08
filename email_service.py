"""
Email service module for sending emails using AWS SES and MJML templates.
"""
import boto3
from botocore.exceptions import ClientError
import os
import re
import mjml

# Template paths
FEEDBACK_TEMPLATE = "templates/feedback_email_template.mjml"
REGISTER_TEMPLATE = "templates/register_email_template.mjml"
ASSETS_DIR = "assets"

# Email subjects
FEEDBACK_SUBJECT = "Thank you for your feedback! - MegaGoal"
REGISTER_SUBJECT = "Welcome to MegaGoal! 🎉"


# Images are now hardcoded as public URLs in templates
# No need for base64 image loading functions

def load_mjml_template(template_path, username=None):
    """
    Load MJML email template from file, compile to HTML, and inject images and username.
    
    Args:
        template_path: Path to the MJML template file
        username: Optional username to personalize the email
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(script_dir, template_path)
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            mjml_content = f.read()
        
        # Images are now hardcoded in templates as public URLs
        # No need to replace placeholders anymore
        
        # Replace username placeholder
        if username:
            # Add space before username if not already present in template
            username_placeholder = "{{USERNAME}}"
            username_replacement = f", {username}" if username else ""
            mjml_content = mjml_content.replace(username_placeholder, username_replacement)
        else:
            # Remove the placeholder if no username provided
            mjml_content = mjml_content.replace("{{USERNAME}}", "")
        
        # Compile MJML to HTML
        html_output = mjml.mjml_to_html(mjml_content)
        if html_output.get('errors'):
            raise Exception(f"MJML compilation errors: {html_output['errors']}")
        
        return html_output['html']
    except FileNotFoundError:
        raise FileNotFoundError(f"MJML template not found at: {template_file}")
    except Exception as e:
        raise Exception(f"Error processing MJML template: {e}")


class EmailService:
    """Service for sending emails via AWS SES."""
    
    def __init__(self, sender, aws_region, sender_name=None):
        """
        Initialize the email service.
        
        Args:
            sender: Email address to send from (must be verified in SES)
            aws_region: AWS region for SES (e.g., 'eu-west-1')
            sender_name: Optional display name for the sender (e.g., 'MegaGoal')
        """
        # Format sender with display name if provided
        if sender_name:
            self.sender = f'"{sender_name}" <{sender}>'
        else:
            self.sender = sender
        
        # Explicitly get credentials from environment variables to ensure they're used
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_session_token = os.getenv('AWS_SESSION_TOKEN')  # Optional, for temporary credentials
        
        # Create boto3 client with explicit credentials if available
        # This ensures we use environment variables instead of checking for credentials file
        if aws_access_key_id and aws_secret_access_key:
            session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token if aws_session_token else None,
                region_name=aws_region
            )
            self.ses_client = session.client('ses', region_name=aws_region)
        else:
            # Fallback to default credential chain (for local development with AWS CLI)
            self.ses_client = boto3.client('ses', region_name=aws_region)
    
    def send_email(self, recipient, template_type='feedback', username=None, subject=None):
        """
        Send an email using the specified template.
        
        Args:
            recipient: Email address of the recipient
            template_type: Type of template to use ('feedback' or 'register')
            username: Optional username to personalize the email
            subject: Optional custom subject (uses default if not provided)
        
        Returns:
            dict: Response from SES with MessageId on success
        
        Raises:
            Exception: If template type is invalid or email sending fails
        """
        # Select template and defaults
        if template_type == 'feedback':
            template_path = FEEDBACK_TEMPLATE
            default_subject = FEEDBACK_SUBJECT
        elif template_type == 'register':
            template_path = REGISTER_TEMPLATE
            default_subject = REGISTER_SUBJECT
        else:
            raise ValueError(f"Invalid template type: {template_type}. Must be 'feedback' or 'register'")
        
        # Load and compile template with username
        html_body = load_mjml_template(template_path, username=username)
        
        # Use provided subject or default
        email_subject = subject or default_subject
        
        # Generate simple plain text version from HTML (for email clients that don't support HTML)
        # Remove HTML tags and get basic text
        text_body = re.sub(r'<[^>]+>', '', html_body)
        text_body = re.sub(r'\s+', ' ', text_body).strip()
        if not text_body:
            text_body = email_subject  # Fallback to subject if extraction fails
        
        try:
            response = self.ses_client.send_email(
                Source=self.sender,
                Destination={
                    'ToAddresses': [recipient],
                },
                Message={
                    'Subject': {'Data': email_subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': text_body}
                    },
                },
            )
            return response
        except ClientError as e:
            raise Exception(f"Failed to send email: {e.response['Error']['Message']}")

