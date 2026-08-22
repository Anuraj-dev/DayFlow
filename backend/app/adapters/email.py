from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailAdapter:
    def send(self, message: EmailMessage) -> None:
        raise NotImplementedError


class ConsoleEmailAdapter(EmailAdapter):
    """Hackathon stand-in until SMTP exists. Prints the invite or reset payload."""

    def send(self, message: EmailMessage) -> None:
        print(f"[dayflow email] to={message.to} subject={message.subject}\n{message.body}")


email_adapter: EmailAdapter = ConsoleEmailAdapter()
