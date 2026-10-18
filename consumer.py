#!/usr/bin/env python3
"""
RabbitMQ consumer service for processing email sending requests.
Consumes messages from the queue and sends emails using the appropriate template.
"""
import os
import json
import time
import logging
from dotenv import load_dotenv
import pika
from email_service import EmailService

# Configure logging first (basic setup)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
# Read ENV variable from docker-compose (defaults to 'development')
env = os.getenv('ENV', 'development')

# Load the appropriate .env file based on ENV variable
# override=False ensures docker-compose environment variables take precedence
env_file = f'.env.{env}'
if os.path.exists(env_file):
    load_dotenv(env_file, override=False)
    logger.info(f"Loaded environment file: {env_file}")
else:
    logger.warning(f"Environment file {env_file} not found. Using system environment variables only.")

# Configuration from environment
MEGAQUEUE_URI = os.getenv('MEGAQUEUE_URI')
QUEUE_NAME = os.getenv('QUEUE_NAME', 'mailing')
AWS_REGION = os.getenv('AWS_REGION', 'eu-west-1')
SENDER = os.getenv('SENDER', 'no-reply@megagera.com')
SENDER_NAME = os.getenv('SENDER_NAME', 'MegaGoal')  # Display name in email clients
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

VALID_TEMPLATES = ('feedback', 'register', 'daily_resume')

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    logger.error("⚠ AWS credentials not found! Email sending will fail.")
    logger.error("   Make sure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set in your .env file")

# Initialize email service
email_service = EmailService(sender=SENDER, aws_region=AWS_REGION, sender_name=SENDER_NAME)


def process_message(ch, method, properties, body):
    """
    Process a message from RabbitMQ queue.
    
    Expected message format (JSON):
    {
        "recipient": "user@example.com",  # optional for daily_resume (uses ADMIN_EMAIL)
        "template": "feedback" | "register" | "daily_resume",
        "username": "Optional username for personalization",
        "subject": "Optional custom subject",
        "stats": { ... }  # required for daily_resume
    }
    """
    try:
        # Parse message
        message = json.loads(body.decode('utf-8'))
        logger.info(f"Received message: {message}")

        template_type = message.get('template', 'feedback')  # Default to feedback
        if template_type not in VALID_TEMPLATES:
            raise ValueError(
                f"Invalid template type: {template_type}. "
                "Must be 'feedback', 'register', or 'daily_resume'"
            )

        recipient = message.get('recipient')
        if not recipient and template_type == 'daily_resume':
            recipient = ADMIN_EMAIL

        if not recipient:
            raise ValueError("Missing required field: 'recipient' (or ADMIN_EMAIL for daily_resume)")

        if template_type == 'daily_resume' and not message.get('stats'):
            raise ValueError("Missing required field: 'stats' for daily_resume template")

        username = message.get('username')  # Optional username

        # Send email
        logger.info(
            f"Sending {template_type} email to {recipient}"
            + (f" (username: {username})" if username else "")
        )
        response = email_service.send_email(
            recipient=recipient,
            template_type=template_type,
            username=username,
            subject=message.get('subject'),
            stats=message.get('stats')
        )
        
        logger.info(f"Email sent successfully! Message ID: {response['MessageId']}")
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse message as JSON: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except ValueError as e:
        logger.error(f"Invalid message format: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error processing message: {error_message}")
        
        # Determine if this is a permanent error (don't requeue) or transient (requeue)
        permanent_errors = [
            "Email address is not verified",
            "not verified",
            "Invalid template type",
            "Missing required field",
            "MJML compilation errors",
            "Error processing MJML template",
            "MJML compilation returned empty HTML",
        ]
        
        is_permanent = any(permanent_error.lower() in error_message.lower() for permanent_error in permanent_errors)
        
        if is_permanent:
            logger.error("Permanent error detected - message will NOT be requeued")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            logger.warning("Transient error detected - message will be requeued for retry")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """Start the RabbitMQ consumer."""
    logger.info("Starting email consumer service...")
    logger.info(f"Connecting to RabbitMQ: {MEGAQUEUE_URI}")
    logger.info(f"Queue name: {QUEUE_NAME}")
    
    connection = None
    channel = None
    
    while True:
        try:
            # Parse connection URI
            params = pika.URLParameters(MEGAQUEUE_URI)
            
            # Create connection
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # Declare queue (creates if it doesn't exist)
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            # Set QoS to process one message at a time
            channel.basic_qos(prefetch_count=1)
            
            # Set up consumer
            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_message
            )
            
            logger.info("Waiting for messages. To exit press CTRL+C")
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            if channel:
                channel.stop_consuming()
            if connection:
                connection.close()
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            if connection and not connection.is_closed:
                connection.close()


if __name__ == "__main__":
    start_consumer()

