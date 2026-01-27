import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings

class EmailService:
    def send_verification_email(self, email: str, verify_link: str) -> None:
        subject = "Verify Your Email Address"
        body = self._build_verification_body(verify_link)

        self._send_email(
            to_email=email,
            subject=subject,
            body=body,
        )

    def _build_verification_body(self, verify_link: str) -> str:
        return (
            "Hello,\n\n"
            "We received a request to verify your email address.\n\n"
            "Please click the link below to complete verification:\n"
            f"{verify_link}\n\n"
            "This link is valid for 15 minutes.\n\n"
            "If you did not request this verification, you can safely ignore this email.\n\n"
            "Best regards,\n"
            "Support Team"
        )

    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email = settings.require_smtp()

        message = MIMEMultipart()
        message["From"] = smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()

            server.login(
                smtp_username,
                smtp_password,
            )

            server.send_message(message)
