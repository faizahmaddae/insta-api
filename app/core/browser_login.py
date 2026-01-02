"""
Browser-based Instagram login using Playwright.
This avoids checkpoint challenges by using a real browser.
"""

import asyncio
import json
import pickle
from pathlib import Path
from typing import Optional
import time

from playwright.async_api import async_playwright, Page, Browser
from app.core.logging import logger
from app.core.config import get_settings


class BrowserLogin:
    """
    Handle Instagram login through a real browser.
    This bypasses most checkpoint challenges.
    """
    
    INSTAGRAM_URL = "https://www.instagram.com"
    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    
    def __init__(self):
        self.settings = get_settings()
        self.sessions_path = self.settings.session_path
        self.sessions_path.mkdir(parents=True, exist_ok=True)
    
    async def login_with_browser(
        self,
        username: str,
        password: str,
        headless: bool = False,  # Set False to see the browser
        timeout: int = 120  # Seconds to wait for manual challenge completion
    ) -> dict:
        """
        Login to Instagram using a real browser.
        
        Args:
            username: Instagram username or email
            password: Instagram password
            headless: If False, shows browser window (useful for challenges)
            timeout: Max seconds to wait for login completion
            
        Returns:
            dict with success status and session cookies
        """
        async with async_playwright() as p:
            # Launch browser (non-headless to handle challenges)
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ]
            )
            
            # Create context with realistic settings
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
            )
            
            page = await context.new_page()
            
            try:
                result = await self._perform_login(
                    page, browser, context, username, password, timeout
                )
                return result
            finally:
                await browser.close()
    
    async def _perform_login(
        self,
        page: Page,
        browser: Browser,
        context,
        username: str,
        password: str,
        timeout: int
    ) -> dict:
        """Perform the actual login process."""
        
        logger.info(f"Starting browser login for {username}")
        
        # Go to Instagram login page
        await page.goto(self.LOGIN_URL, wait_until='networkidle')
        await asyncio.sleep(2)
        
        # Handle cookie consent if present
        try:
            cookie_btn = page.locator('button:has-text("Allow all cookies")')
            if await cookie_btn.count() > 0:
                await cookie_btn.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Try to accept cookies (different button text)
        try:
            cookie_btn = page.locator('button:has-text("Accept")')
            if await cookie_btn.count() > 0:
                await cookie_btn.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Fill login form
        try:
            # Wait for login form
            await page.wait_for_selector('input[name="username"]', timeout=10000)
            
            # Enter credentials
            await page.fill('input[name="username"]', username)
            await asyncio.sleep(0.5)
            await page.fill('input[name="password"]', password)
            await asyncio.sleep(0.5)
            
            # Click login button
            login_btn = page.locator('button[type="submit"]')
            await login_btn.click()
            
            logger.info("Credentials submitted, waiting for response...")
            
        except Exception as e:
            logger.error(f"Failed to fill login form: {e}")
            return {"success": False, "error": f"Login form error: {e}"}
        
        # Wait for login to complete or challenge to appear
        start_time = time.time()
        logged_in = False
        
        while time.time() - start_time < timeout:
            await asyncio.sleep(2)
            
            current_url = page.url
            
            # Check if logged in (redirected to home)
            if "instagram.com" in current_url and "/accounts/login" not in current_url:
                # Check for logged-in indicators
                try:
                    # Look for home feed or profile elements
                    home_indicator = await page.query_selector('svg[aria-label="Home"]')
                    if home_indicator:
                        logged_in = True
                        logger.info("Login successful!")
                        break
                except:
                    pass
            
            # Check for "Save Your Login Info?" prompt (means we're logged in)
            try:
                save_info = page.locator('text="Save your login info?"')
                if await save_info.count() > 0:
                    logged_in = True
                    logger.info("Login successful (save info prompt detected)")
                    # Click "Not Now" to skip
                    not_now = page.locator('button:has-text("Not Now")')
                    if await not_now.count() > 0:
                        await not_now.click()
                    break
            except:
                pass
            
            # Check for "Turn on Notifications?" prompt
            try:
                notif_prompt = page.locator('text="Turn on Notifications"')
                if await notif_prompt.count() > 0:
                    logged_in = True
                    logger.info("Login successful (notification prompt detected)")
                    not_now = page.locator('button:has-text("Not Now")')
                    if await not_now.count() > 0:
                        await not_now.click()
                    break
            except:
                pass
            
            # Check for error messages
            try:
                error_msg = page.locator('text="Sorry, your password was incorrect"')
                if await error_msg.count() > 0:
                    return {"success": False, "error": "Invalid password"}
            except:
                pass
            
            # If challenge/checkpoint, wait for user to solve it
            if "challenge" in current_url or "checkpoint" in current_url:
                logger.info("Challenge detected - please complete it in the browser...")
        
        if not logged_in:
            return {
                "success": False,
                "error": "Login timeout - challenge may require manual completion"
            }
        
        # Get cookies
        cookies = await context.cookies()
        
        # Save session
        session_file = self.sessions_path / f"browser-session-{username}.json"
        with open(session_file, 'w') as f:
            json.dump(cookies, f)
        
        logger.info(f"Session saved to {session_file}")
        
        # Convert to Instaloader format
        await self._convert_to_instaloader_session(username, cookies)
        
        return {
            "success": True,
            "username": username,
            "cookies_count": len(cookies),
            "session_file": str(session_file)
        }
    
    async def _convert_to_instaloader_session(self, username: str, cookies: list):
        """Convert browser cookies to Instaloader session format."""
        import requests
        
        # Create a requests session with the cookies
        session = requests.Session()
        
        for cookie in cookies:
            session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', '.instagram.com'),
                path=cookie.get('path', '/')
            )
        
        # Save in Instaloader format
        session_file = self.sessions_path / f"session-{username}"
        with open(session_file, 'wb') as f:
            pickle.dump(session.cookies, f)
        
        logger.info(f"Converted session to Instaloader format: {session_file}")
    
    async def login_all_accounts(
        self,
        accounts: list[dict],
        headless: bool = False,
        delay_between: int = 5
    ) -> list[dict]:
        """
        Login multiple accounts sequentially.
        
        Args:
            accounts: List of {"username": str, "password": str}
            headless: Show browser or not
            delay_between: Seconds between logins
            
        Returns:
            List of results for each account
        """
        results = []
        
        for i, account in enumerate(accounts):
            logger.info(f"Logging in account {i+1}/{len(accounts)}: {account['username']}")
            
            result = await self.login_with_browser(
                username=account['username'],
                password=account['password'],
                headless=headless
            )
            
            results.append({
                "username": account['username'],
                **result
            })
            
            if i < len(accounts) - 1:
                logger.info(f"Waiting {delay_between}s before next login...")
                await asyncio.sleep(delay_between)
        
        return results


# CLI helper for manual login
async def interactive_login(username: str, password: str):
    """Run interactive browser login (shows browser window)."""
    login = BrowserLogin()
    result = await login.login_with_browser(
        username=username,
        password=password,
        headless=False,  # Show browser
        timeout=180  # 3 minutes to complete any challenges
    )
    return result


if __name__ == "__main__":
    # CLI usage: python -m app.core.browser_login
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m app.core.browser_login <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    result = asyncio.run(interactive_login(username, password))
    print(json.dumps(result, indent=2))
