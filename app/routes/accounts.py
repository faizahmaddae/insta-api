"""
Account management routes for multi-account support.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.accounts import get_account_manager
from app.core.logging import logger


router = APIRouter(tags=["Accounts"])


class AddAccountRequest(BaseModel):
    username: str
    password: str
    notes: Optional[str] = ""


class AccountResponse(BaseModel):
    success: bool
    message: str


@router.get(
    "/stats",
    summary="Get Account Statistics",
    description="Get statistics for all managed Instagram accounts."
)
async def get_account_stats():
    """Get account pool statistics."""
    manager = get_account_manager()
    return manager.get_stats()


@router.post(
    "/load",
    response_model=AccountResponse,
    summary="Load Accounts from File",
    description="Load accounts from accounts.json file."
)
async def load_accounts(filepath: str = "accounts.json"):
    """Load accounts from JSON file."""
    manager = get_account_manager()
    count = manager.load_from_file(filepath)
    
    if count > 0:
        return AccountResponse(
            success=True,
            message=f"Loaded {count} accounts from {filepath}"
        )
    else:
        return AccountResponse(
            success=False,
            message=f"No accounts loaded from {filepath}. File may not exist or be empty."
        )


@router.post(
    "/add",
    response_model=AccountResponse,
    summary="Add Account",
    description="Add a new Instagram account to the pool."
)
async def add_account(request: AddAccountRequest):
    """Add a new account to the rotation pool."""
    manager = get_account_manager()
    
    if manager.add_account(request.username, request.password, request.notes):
        return AccountResponse(
            success=True,
            message=f"Account {request.username} added successfully"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Account {request.username} already exists"
        )


@router.delete(
    "/{username}",
    response_model=AccountResponse,
    summary="Remove Account",
    description="Remove an Instagram account from the pool."
)
async def remove_account(username: str):
    """Remove an account from the rotation pool."""
    manager = get_account_manager()
    
    if manager.remove_account(username):
        return AccountResponse(
            success=True,
            message=f"Account {username} removed successfully"
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Account {username} not found"
        )


@router.post(
    "/{username}/enable",
    response_model=AccountResponse,
    summary="Enable Account",
    description="Enable a disabled account."
)
async def enable_account(username: str):
    """Enable an account for use."""
    manager = get_account_manager()
    account = manager.get_account_by_username(username)
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {username} not found")
    
    account.enabled = True
    return AccountResponse(success=True, message=f"Account {username} enabled")


@router.post(
    "/{username}/disable",
    response_model=AccountResponse,
    summary="Disable Account",
    description="Disable an account (won't be used for requests)."
)
async def disable_account(username: str):
    """Disable an account from being used."""
    manager = get_account_manager()
    account = manager.get_account_by_username(username)
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {username} not found")
    
    account.enabled = False
    return AccountResponse(success=True, message=f"Account {username} disabled")


@router.get(
    "/next",
    summary="Preview Next Account",
    description="Preview which account will be used for the next request (doesn't consume a rotation)."
)
async def preview_next_account():
    """Preview the next account in rotation without consuming it."""
    manager = get_account_manager()
    
    # Temporarily get next account
    account = manager.get_next_account()
    
    if account:
        # Move index back since we just want to preview
        with manager._accounts_lock:
            manager._current_index = (manager._current_index - 1) % len(manager._accounts) if manager._accounts else 0
        
        return {
            "next_account": account.username,
            "requests_this_hour": account.requests_this_hour,
            "is_available": account.is_available,
            "message": "This account will be used for the next authenticated request"
        }
    else:
        return {
            "next_account": None,
            "message": "No accounts configured or all accounts are rate limited/disabled"
        }


@router.post(
    "/{username}/test",
    summary="Test Account Login",
    description="Test if an account can successfully login to Instagram."
)
async def test_account_login(username: str):
    """Test login for a specific account."""
    from app.services.instaloader_service import get_instaloader_service
    
    manager = get_account_manager()
    account = manager.get_account_by_username(username)
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {username} not found")
    
    service = get_instaloader_service()
    
    try:
        # Try to get/create a loader for this account (will login if needed)
        loader = service._get_loader_for_account(account)
        
        # Test if login is valid
        test_user = loader.test_login()
        
        if test_user:
            return {
                "success": True,
                "username": username,
                "logged_in_as": test_user,
                "message": "Account login successful"
            }
        else:
            return {
                "success": False,
                "username": username,
                "message": "Session exists but may be expired"
            }
    except Exception as e:
        account.last_error = str(e)
        raise HTTPException(
            status_code=400,
            detail=f"Login failed for {username}: {str(e)}"
        )


@router.post(
    "/{username}/browser-login",
    summary="Login via Browser",
    description="Login using Playwright browser - handles challenges automatically."
)
async def browser_login(username: str, headless: bool = False):
    """
    Login to Instagram using a real browser.
    This handles checkpoints/challenges that block direct login.
    
    Set headless=False to see the browser window and manually solve challenges.
    """
    from app.core.browser_login import BrowserLogin
    
    manager = get_account_manager()
    account = manager.get_account_by_username(username)
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {username} not found")
    
    login_helper = BrowserLogin()
    
    try:
        result = await login_helper.login_with_browser(
            username=account.username,
            password=account.password,
            headless=headless,
            timeout=180  # 3 minutes for manual challenge
        )
        
        if result["success"]:
            account.last_error = None
            return {
                "success": True,
                "username": username,
                "message": "Browser login successful! Session saved.",
                "cookies": result.get("cookies_count", 0)
            }
        else:
            account.last_error = result.get("error")
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Browser login failed")
            )
    except HTTPException:
        raise
    except Exception as e:
        account.last_error = str(e)
        raise HTTPException(
            status_code=500,
            detail=f"Browser login error: {str(e)}"
        )


@router.post(
    "/browser-login-all",
    summary="Login All Accounts via Browser",
    description="Login all enabled accounts using Playwright browser."
)
async def browser_login_all(headless: bool = False, delay: int = 5):
    """
    Login all accounts using browser.
    
    Args:
        headless: Show browser windows or not
        delay: Seconds between logins
    """
    from app.core.browser_login import BrowserLogin
    
    manager = get_account_manager()
    stats = manager.get_stats()
    
    accounts_to_login = [
        {"username": acc["username"], "password": manager.get_account_by_username(acc["username"]).password}
        for acc in stats["accounts"]
        if acc["enabled"]
    ]
    
    if not accounts_to_login:
        raise HTTPException(status_code=400, detail="No enabled accounts to login")
    
    login_helper = BrowserLogin()
    results = await login_helper.login_all_accounts(
        accounts=accounts_to_login,
        headless=headless,
        delay_between=delay
    )
    
    success_count = sum(1 for r in results if r.get("success"))
    
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results
    }
