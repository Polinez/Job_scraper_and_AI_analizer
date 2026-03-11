import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List
from src.models import JobAnalysis
from src.utils.logger import logger

class NotificationService:
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender = sender_email
        self.password = sender_password
        self.recipient = recipient_email

    def _generate_html_body(self, analysis_results: List[JobAnalysis]) -> str:
        job_blocks = []
        for item in analysis_results:
            score = item.analysis.match_score
            color = "#28a745" if score >= 70 else "#ffc107" if score >= 45 else "#dc3545"

            block = f"""
                <div style="margin-bottom: 20px; padding: 10px; border-left: 5px solid {color}; background-color: #f9f9f9;">
                    <h3 style="margin: 0;">{item.title} - <span style="color: #666;">{item.company}</span></h3>
                    <p style="margin: 5px 0;"><b>Dopasowanie:</b> <span style="color: {color}; font-size: 1.2em;">{score}/100</span></p>
                    <p style="margin: 5px 0;"><b>Rekomendacja:</b> {item.analysis.advice}</p>
                    <a href="{item.url}" style="color: #007bff;">Otwórz ofertę →</a>
                </div>"""
            job_blocks.append(block)

        return f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <h2 style="color: #2d5a27;">Wyniki analizy ofert pracy ({len(analysis_results)})</h2>
                    <hr>
                    {"".join(job_blocks)}
                </body>
            </html>"""

    def send_summary_email(self, analysis_results: List[JobAnalysis]):
        if not all([self.sender, self.password, self.recipient]):
            logger.error("Błąd: Brak pełnej konfiguracji e-mail w .env")
            return

        html_body = self._generate_html_body(analysis_results)
        
        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = self.recipient
        msg['Subject'] = f"Raport ofert - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg.attach(MIMEText(html_body, 'html'))

        try:
            with smtplib.SMTP("smtp.mail.yahoo.com", 587) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            logger.info("E-mail wysłany pomyślnie!")
        except Exception as e:
            logger.error(f"Błąd wysyłki e-mail: {e}")
