# MegaMail - Email Microservice

A microservice for sending emails using AWS SES and MJML templates, integrated with RabbitMQ for message queue processing.

## Features

- 🎨 **MJML Email Templates**: Beautiful, responsive email templates
- 📧 **AWS SES Integration**: Send emails via Amazon Simple Email Service
- 🐰 **RabbitMQ Consumer**: Process email requests from message queues
- 🐳 **Docker Support**: Full Docker and Docker Compose setup
- 📝 **Multiple Templates**: Support for feedback and registration emails

## How It Works

MegaMail is a message queue-based email service that processes email requests from RabbitMQ. The service:

1. **Listens to RabbitMQ queues** for email requests
2. **Processes messages** containing recipient information and template types
3. **Renders MJML templates** into HTML email content
4. **Sends emails** via AWS SES to the specified recipients

The microservice supports multiple email templates (feedback, registration, etc.) and can be deployed using Docker for easy integration into larger systems.

## Project Structure

```
MegaMail/
├── assets/              # Image assets for emails
├── templates/           # MJML email templates
│   ├── feedback_email_template.mjml
│   └── register_email_template.mjml
├── consumer.py          # RabbitMQ consumer service
├── email_service.py     # Email sending service
├── docker-compose.yml   # Docker Compose configuration
├── Dockerfile           # Docker image definition
└── requirements.txt     # Python dependencies
```

## License

This project is licensed under the GPL-3.0 License. See the LICENSE file for details.

## Contact & Collaborate

Contact with me to collaborate :)

- gera1397@gmail.com
- GitHub: [MegaGera](https://github.com/MegaGera)
