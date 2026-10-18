"""
Email service module for sending emails using AWS SES and MJML templates.
"""
import boto3
from botocore.exceptions import ClientError
import html
import os
import re
import mjml

# Template paths
FEEDBACK_TEMPLATE = "templates/feedback_email_template.mjml"
REGISTER_TEMPLATE = "templates/register_email_template.mjml"
DAILY_RESUME_TEMPLATE = "templates/daily_resume_email_template.mjml"

# Email subjects
FEEDBACK_SUBJECT = "Thank you for your feedback! - MegaGoal"
REGISTER_SUBJECT = "Welcome to MegaGoal! 🎉"
DAILY_RESUME_SUBJECT = "Mega daily resume"


def _metric_row(label, value):
    safe_label = html.escape(str(label))
    safe_value = html.escape(str(value))
    return (
        f'<div class="metric-row">'
        f'<span class="metric-label">{safe_label}</span>'
        f'<span class="metric-value">{safe_value}</span>'
        f'</div>'
    )


def _build_auth_html(auth):
    auth = auth or {}
    parts = [
        _metric_row('New users', auth.get('newUsersCount', 0)),
        _metric_row('Total logins', auth.get('loginsTotal', 0)),
        _metric_row('Normal logins', auth.get('loginsNormal', 0)),
        _metric_row('Test logins', auth.get('loginsTest', 0)),
        _metric_row('Distinct users logged in', auth.get('distinctLoginUsers', 0)),
    ]

    if auth.get('passwordChanged'):
        parts.append(_metric_row('Password changes', auth.get('passwordChanged', 0)))
    if auth.get('passwordReset'):
        parts.append(_metric_row('Password resets', auth.get('passwordReset', 0)))
    if auth.get('testUsersCreated'):
        parts.append(_metric_row('Test users created', auth.get('testUsersCreated', 0)))

    new_users = auth.get('newUsers') or []
    if new_users:
        parts.append('<p style="margin:14px 0 6px 0;color:#444;font-size:13px;font-weight:600;">New registrations</p>')
        for user in new_users:
            username = html.escape(str(user.get('username') or 'unknown'))
            email = user.get('email')
            if email:
                parts.append(
                    f'<p class="user-line">• <strong>{username}</strong> '
                    f'&lt;{html.escape(str(email))}&gt;</p>'
                )
            else:
                parts.append(f'<p class="user-line">• <strong>{username}</strong> <span class="muted">(no email)</span></p>')
    elif auth.get('newUsersCount', 0) == 0:
        parts.append('<p class="muted" style="margin-top:10px;">No new registrations in this period.</p>')

    return ''.join(parts)


def _build_megagoal_html(goal):
    goal = goal or {}
    interactions = goal.get('interactions') or {}
    parts = [
        _metric_row('Distinct users', goal.get('distinctUsers', 0)),
        _metric_row('Sessions (≥30 min gap)', goal.get('sessions', 0)),
        _metric_row('Matches created', goal.get('matchesCreated', 0)),
        _metric_row('Matches deleted', goal.get('matchesDeleted', 0)),
        _metric_row('Interactions (total)', interactions.get('total', 0)),
        _metric_row('Reactions', interactions.get('reaction', 0)),
        _metric_row('Match ratings', interactions.get('match_rating', 0)),
        _metric_row('Player votes', interactions.get('player_voted', 0)),
        _metric_row('Favourite teams added', goal.get('favouriteTeamsAdded', 0)),
        _metric_row('Favourite leagues added', goal.get('favouriteLeaguesAdded', 0)),
        _metric_row('Feedback submitted', goal.get('feedbackSubmitted', 0)),
    ]

    page_views = goal.get('pageViews') or []
    if page_views:
        parts.append('<p style="margin:14px 0 8px 0;color:#444;font-size:13px;font-weight:600;">Page views</p>')
        for item in page_views:
            page = html.escape(str(item.get('page') or 'unknown'))
            count = html.escape(str(item.get('count', 0)))
            parts.append(f'<span class="chip">{page}: {count}</span>')
    else:
        parts.append('<p class="muted" style="margin-top:10px;">No page views logged in this period.</p>')

    return ''.join(parts)


def load_mjml_template(template_path, username=None, replacements=None):
    """
    Load MJML email template from file, compile to HTML, and inject placeholders.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(script_dir, template_path)
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            mjml_content = f.read()

        if username:
            mjml_content = mjml_content.replace("{{USERNAME}}", f", {username}")
        else:
            mjml_content = mjml_content.replace("{{USERNAME}}", "")

        if replacements:
            for key, value in replacements.items():
                mjml_content = mjml_content.replace(f"{{{{{key}}}}}", str(value))

        html_output = mjml.mjml_to_html(mjml_content)
        # mjml may return a dict or a ParseResult-like object
        if isinstance(html_output, dict):
            errors = html_output.get('errors')
            html_body = html_output.get('html')
        else:
            errors = getattr(html_output, 'errors', None)
            html_body = getattr(html_output, 'html', None)

        if errors:
            raise Exception(f"MJML compilation errors: {errors}")
        if not html_body:
            raise Exception("MJML compilation returned empty HTML")

        return html_body
    except FileNotFoundError:
        raise FileNotFoundError(f"MJML template not found at: {template_file}")
    except Exception as e:
        raise Exception(f"Error processing MJML template: {e}")


class EmailService:
    """Service for sending emails via AWS SES."""

    def __init__(self, sender, aws_region, sender_name=None):
        if sender_name:
            self.sender = f'"{sender_name}" <{sender}>'
        else:
            self.sender = sender

        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_session_token = os.getenv('AWS_SESSION_TOKEN')

        if aws_access_key_id and aws_secret_access_key:
            session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token if aws_session_token else None,
                region_name=aws_region
            )
            self.ses_client = session.client('ses', region_name=aws_region)
        else:
            self.ses_client = boto3.client('ses', region_name=aws_region)

    def send_email(self, recipient, template_type='feedback', username=None, subject=None, stats=None):
        """
        Send an email using the specified template.
        """
        if template_type == 'feedback':
            template_path = FEEDBACK_TEMPLATE
            default_subject = FEEDBACK_SUBJECT
            replacements = None
        elif template_type == 'register':
            template_path = REGISTER_TEMPLATE
            default_subject = REGISTER_SUBJECT
            replacements = None
        elif template_type == 'daily_resume':
            template_path = DAILY_RESUME_TEMPLATE
            default_subject = DAILY_RESUME_SUBJECT
            stats = stats or {}
            period = stats.get('period') or {}
            replacements = {
                'PERIOD_LABEL': html.escape(str(period.get('label') or 'Last 24 hours')),
                'AUTH_HTML': _build_auth_html(stats.get('megaauth')),
                'MEGAGOAL_HTML': _build_megagoal_html(stats.get('megagoal')),
            }
        else:
            raise ValueError(
                f"Invalid template type: {template_type}. "
                "Must be 'feedback', 'register', or 'daily_resume'"
            )

        html_body = load_mjml_template(template_path, username=username, replacements=replacements)
        email_subject = subject or default_subject

        text_body = re.sub(r'<[^>]+>', '', html_body)
        text_body = re.sub(r'\s+', ' ', text_body).strip()
        if not text_body:
            text_body = email_subject

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
