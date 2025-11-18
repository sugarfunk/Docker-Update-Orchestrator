import httpx
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via multiple channels"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def send_notification(self, title: str, message: str,
                               priority: str = "normal",
                               channels: Optional[List[str]] = None,
                               container_name: Optional[str] = None,
                               server_name: Optional[str] = None,
                               action_buttons: Optional[List[Dict]] = None,
                               url: Optional[str] = None) -> Dict[str, bool]:
        """
        Send notification via multiple channels
        Returns: {channel: success_status}
        """
        results = {}

        if channels is None:
            channels = []
            if settings.NTFY_ENABLED:
                channels.append("ntfy")
            if settings.EMAIL_ENABLED:
                channels.append("email")
            if settings.WEBHOOK_ENABLED:
                channels.append("webhook")

        for channel in channels:
            try:
                if channel == "ntfy":
                    success = await self._send_ntfy(title, message, priority, url, action_buttons)
                    results["ntfy"] = success
                elif channel == "email":
                    success = await self._send_email(title, message, priority, container_name, server_name)
                    results["email"] = success
                elif channel == "webhook":
                    success = await self._send_webhook(title, message, priority, container_name, server_name, url)
                    results["webhook"] = success
            except Exception as e:
                logger.error(f"Error sending notification via {channel}: {str(e)}")
                results[channel] = False

        return results

    async def _send_ntfy(self, title: str, message: str, priority: str,
                        url: Optional[str], actions: Optional[List[Dict]]) -> bool:
        """Send notification via NTFY"""
        try:
            ntfy_url = f"{settings.NTFY_SERVER}/{settings.NTFY_TOPIC}"

            # Map priority
            ntfy_priority = {
                "low": "2",
                "normal": "3",
                "high": "4",
                "urgent": "5"
            }.get(priority, "3")

            headers = {
                "Title": title,
                "Priority": ntfy_priority,
                "Tags": self._get_ntfy_tags(priority)
            }

            if url:
                headers["Click"] = url

            # Add action buttons
            if actions:
                actions_str = ", ".join([
                    f"view, {action['label']}, {action['url']}"
                    for action in actions[:3]  # Max 3 actions
                ])
                headers["Actions"] = actions_str

            response = await self.http_client.post(
                ntfy_url,
                content=message,
                headers=headers
            )

            success = response.status_code == 200
            if success:
                logger.info(f"NTFY notification sent: {title}")
            else:
                logger.error(f"NTFY notification failed: {response.status_code}")

            return success

        except Exception as e:
            logger.error(f"Error sending NTFY notification: {str(e)}")
            return False

    async def _send_email(self, title: str, message: str, priority: str,
                         container_name: Optional[str], server_name: Optional[str]) -> bool:
        """Send notification via Email"""
        try:
            if not settings.EMAIL_TO:
                logger.warning("No email recipients configured")
                return False

            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = ", ".join(settings.EMAIL_TO)
            msg["Subject"] = f"[Docker Update] {title}"

            # Plain text version
            text_body = f"{message}\n\n"
            if container_name:
                text_body += f"Container: {container_name}\n"
            if server_name:
                text_body += f"Server: {server_name}\n"

            # HTML version
            html_body = f"""
            <html>
                <body>
                    <h2>{title}</h2>
                    <p>{message.replace('\n', '<br>')}</p>
                    {f'<p><strong>Container:</strong> {container_name}</p>' if container_name else ''}
                    {f'<p><strong>Server:</strong> {server_name}</p>' if server_name else ''}
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        Docker Update Orchestrator
                    </p>
                </body>
            </html>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send email
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                start_tls=True
            )

            logger.info(f"Email notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            return False

    async def _send_webhook(self, title: str, message: str, priority: str,
                           container_name: Optional[str], server_name: Optional[str],
                           url: Optional[str]) -> bool:
        """Send notification via Webhook"""
        try:
            if not settings.WEBHOOK_URLS:
                logger.warning("No webhook URLs configured")
                return False

            payload = {
                "title": title,
                "message": message,
                "priority": priority,
                "container_name": container_name,
                "server_name": server_name,
                "url": url,
                "timestamp": datetime.utcnow().isoformat()
            }

            all_success = True
            for webhook_url in settings.WEBHOOK_URLS:
                try:
                    response = await self.http_client.post(
                        webhook_url,
                        json=payload
                    )

                    if response.status_code not in [200, 201, 202]:
                        logger.error(f"Webhook failed for {webhook_url}: {response.status_code}")
                        all_success = False
                except Exception as e:
                    logger.error(f"Error sending to webhook {webhook_url}: {str(e)}")
                    all_success = False

            if all_success:
                logger.info(f"Webhook notifications sent: {title}")

            return all_success

        except Exception as e:
            logger.error(f"Error sending webhook notification: {str(e)}")
            return False

    def _get_ntfy_tags(self, priority: str) -> str:
        """Get NTFY tags based on priority"""
        tags = {
            "low": "information_source",
            "normal": "package",
            "high": "warning",
            "urgent": "rotating_light"
        }
        return tags.get(priority, "package")

    async def send_update_available(self, container_name: str, server_name: str,
                                   from_version: str, to_version: str,
                                   risk_level: str, breaking_changes: bool) -> Dict[str, bool]:
        """Send notification for available update"""
        priority = "high" if breaking_changes else "normal"

        title = f"Update Available: {container_name}"
        message = f"""Container {container_name} on {server_name} has an update available.

From: {from_version}
To: {to_version}
Risk Level: {risk_level}
Breaking Changes: {'Yes' if breaking_changes else 'No'}

Please review the changelog and decide whether to proceed with the update."""

        return await self.send_notification(
            title=title,
            message=message,
            priority=priority,
            container_name=container_name,
            server_name=server_name
        )

    async def send_update_completed(self, container_name: str, server_name: str,
                                   version: str, duration_seconds: int) -> Dict[str, bool]:
        """Send notification for completed update"""
        title = f"Update Completed: {container_name}"
        message = f"""Container {container_name} on {server_name} has been successfully updated.

New Version: {version}
Duration: {duration_seconds}s

The container is now running and health checks have passed."""

        return await self.send_notification(
            title=title,
            message=message,
            priority="normal",
            container_name=container_name,
            server_name=server_name
        )

    async def send_update_failed(self, container_name: str, server_name: str,
                                version: str, error: str) -> Dict[str, bool]:
        """Send notification for failed update"""
        title = f"Update Failed: {container_name}"
        message = f"""Container {container_name} on {server_name} update failed.

Target Version: {version}
Error: {error}

The container may have been rolled back to the previous version. Please check the logs."""

        return await self.send_notification(
            title=title,
            message=message,
            priority="urgent",
            container_name=container_name,
            server_name=server_name
        )

    async def send_rollback_executed(self, container_name: str, server_name: str,
                                    from_version: str, to_version: str,
                                    reason: str) -> Dict[str, bool]:
        """Send notification for rollback"""
        title = f"Rollback Executed: {container_name}"
        message = f"""Container {container_name} on {server_name} has been rolled back.

From: {from_version}
To: {to_version}
Reason: {reason}

Please investigate the issue before attempting another update."""

        return await self.send_notification(
            title=title,
            message=message,
            priority="urgent",
            container_name=container_name,
            server_name=server_name
        )

    async def send_daily_digest(self, updates_count: int, critical_count: int,
                               pending_approvals: int) -> Dict[str, bool]:
        """Send daily digest notification"""
        title = "Docker Updates Daily Digest"
        message = f"""Daily Update Summary:

Updates Available: {updates_count}
Critical Updates: {critical_count}
Pending Approvals: {pending_approvals}

Review your dashboard for details."""

        priority = "high" if critical_count > 0 else "normal"

        return await self.send_notification(
            title=title,
            message=message,
            priority=priority
        )

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


from datetime import datetime

# Global instance
notification_service = NotificationService()
