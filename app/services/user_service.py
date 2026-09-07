from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.repositories.users import UserRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def get_or_create_user(
        self,
        channel: str,
        external_user_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> tuple[User, bool]:
        """
        Returns (user, created).
        """
        existing = await self.user_repo.get_by_channel_and_external_id(channel, external_user_id)
        if existing is not None:
            user = await self.user_repo.create_or_update(
                channel=channel,
                external_user_id=external_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            return user, False

        user = await self.user_repo.create_or_update(
            channel=channel,
            external_user_id=external_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        logger.info(
            "User created",
            extra={
                "extra_fields": {
                    "user_id": str(user.id),
                    "channel": channel,
                    "external_user_id": external_user_id,
                }
            },
        )
        return user, True
