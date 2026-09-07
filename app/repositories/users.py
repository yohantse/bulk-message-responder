from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_channel_and_external_id(
        self, channel: str, external_user_id: str
    ) -> User | None:
        stmt = select(User).where(
            User.channel == channel,
            User.external_user_id == external_user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        channel: str,
        external_user_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        user = await self.get_by_channel_and_external_id(channel, external_user_id)
        if user is None:
            user = User(
                channel=channel,
                external_user_id=external_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            self.session.add(user)
            await self.session.flush()
        else:
            # Update user profile information if changed
            updated = False
            if username is not None and user.username != username:
                user.username = username
                updated = True
            if first_name is not None and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name is not None and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                await self.session.flush()

        return user
