"""Decorators for CRUD operations."""

from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


def transactional(func: Callable[..., T]) -> Callable[..., T]:
    """Decorate a CRUD method to control transaction.

    Allows for a single flag to control commit and refresh,
    defaults to True.

    Example:
    -------
    ```python
    @transactional
    async def create(db: AsyncSession, item: Item):
        db.add(item)
        return item

    # With auto transaction
    await create(db, item)

    # Disable auto transaction for manual control, allows
    # for unit of work control

    try:
        await crud.item.create(db, item_b, auto_transaction=False)
        await crud.item.create(db, item_a, auto_transaction=False)
        db.commit()
        db.refresh(item_a)
        db.refresh(item_b)
    except Exception as e:
        db.rollback()
        ...
    ```

    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """Wrap the function to control transaction.

        Args:
        ----
            *args (Any): The arguments to the function.
            **kwargs (Any): The keyword arguments to the function.

        Returns:
        -------
            T: The result of the function.

        """
        auto_transaction = kwargs.pop("auto_transaction", True)  # default to True
        db: AsyncSession = next(
            (arg for arg in args if isinstance(arg, AsyncSession)), kwargs.get("db")
        )

        try:
            result = await func(*args, **kwargs)
            if auto_transaction:
                await db.commit()
                if result is not None:
                    if isinstance(result, list):
                        for item in result:
                            await db.refresh(item)
                    else:
                        await db.refresh(result)
            return result
        except Exception as e:
            if auto_transaction:
                await db.rollback()
            raise e

    return wrapper
