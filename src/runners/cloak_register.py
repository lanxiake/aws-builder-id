#!/usr/bin/env python3
"""
使用 CloakBrowser Playwright 引擎（humanize + geoip）完成 AWS Builder ID 注册。

相比 UC+Selenium，启用 CloakBrowser 原生 humanize 行为模拟，更适合强风控页面。
"""

from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from cloakbrowser import launch_async

from config import HEADLESS, REGION_CURRENT
from helpers.cloak_driver import resolve_headless
from managers.proxy_manager import proxy_manager
from helpers.account_utils import generate_strong_password, save_account
from services.email_service import create_temp_email, wait_for_verification_email

fake = Faker("en_US")


async def _active_page(browser):
    """获取仍存活的页面（含弹窗）。"""
    for ctx in browser.contexts:
        for p in ctx.pages:
            if not p.is_closed():
                return p
    return None


async def _safe_click_text(page, text: str, timeout: int = 60000):
    """点击包含指定文本的元素。"""
    loc = page.get_by_text(text, exact=False).first
    await loc.wait_for(state="visible", timeout=timeout)
    await loc.scroll_into_view_if_needed()
    await asyncio.sleep(random.uniform(0.5, 1.2))
    await loc.click(timeout=timeout)
async def _click_if_visible(page, selector: str, timeout: int = 8000) -> bool:
    """若元素可见则点击，返回是否成功。"""
    try:
        loc = page.locator(selector).first
        await loc.wait_for(state="visible", timeout=timeout)
        await loc.click()
        return True
    except Exception:
        return False


async def _fill_first(page, selector: str, value: str) -> bool:
    """填写第一个匹配输入框。"""
    try:
        loc = page.locator(selector).first
        await loc.wait_for(state="visible", timeout=15000)
        await loc.click()
        await loc.fill("")
        await loc.type(value, delay=random.randint(40, 120))
        return True
    except Exception as e:
        print(f"   填写失败 {selector}: {e}")
        return False


async def run_cloak_async() -> None:
    """CloakBrowser Playwright 注册主流程。"""
    detected_region = __import__("os").environ.get("AUTO_REGION", REGION_CURRENT)
    effective_headless = resolve_headless(HEADLESS)
    proxy_manager.print_proxy_info()

    proxy_url = None
    if proxy_manager.use_proxy:
        proxy_url = proxy_manager.get_proxy()
        if not proxy_url:
            print("❌ 代理未配置，退出")
            return

    print("📧 创建临时邮箱...")
    email_address, jwt_token = create_temp_email()
    if not email_address:
        print("❌ 邮箱创建失败")
        return
    print(f"   邮箱: {email_address}")

    print(f"🛡️  CloakBrowser Playwright (geoip=True, humanize=False, headless={effective_headless})")
    launch_kwargs = {
        "proxy": proxy_url,
        "geoip": bool(proxy_url),
        "humanize": False,
        "headless": effective_headless,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    browser = await launch_async(**launch_kwargs)
    page = await browser.new_page()
    page.set_default_timeout(90000)

    try:
        print("打开 AWS Builder...")
        await page.goto(
            "https://builder.aws.com/start",
            wait_until="domcontentloaded",
            timeout=120000,
        )
        await asyncio.sleep(random.uniform(5, 8))
        print(f"   标题: {await page.title()}")
        print(f"   URL: {page.url}")

        for sel in [
            "button:has-text('Accept')",
            "#awsccc-cb-btn-accept",
        ]:
            if await _click_if_visible(page, sel, 5000):
                print("✅ Cookie 已接受")
                await asyncio.sleep(random.uniform(2, 3))
                break

        print("点击 Sign up with Builder ID...")
        await asyncio.sleep(random.uniform(2, 4))
        clicked = await page.evaluate(
            """() => {
            const nodes = [...document.querySelectorAll('span,button,a')];
            const el = nodes.find(n => (n.textContent||'').includes('Sign up with Builder ID'));
            if (!el) return false;
            const t = el.closest('button') || el.closest('a') || el;
            t.click();
            return true;
            }"""
        )
        print(f"   JS 点击: {clicked}")
        await asyncio.sleep(random.uniform(6, 10))
        page = await _active_page(browser) or page
        print(f"   URL: {page.url}")

        await _fill_first(page, 'input[placeholder="username@example.com"]', email_address)
        await page.locator('[data-testid="test-primary-button"]').first.click()
        await asyncio.sleep(random.uniform(3, 5))
        print(f"   邮箱页完成: {page.url}")

        first_name = fake.first_name()
        last_name = fake.last_name()
        full_name = f"{first_name} {last_name}"
        print(f"填写姓名: {full_name}")

        text_inputs = page.locator('input[type="text"]')
        count = await text_inputs.count()
        if count >= 2:
            await text_inputs.nth(0).click()
            await text_inputs.nth(0).type(first_name, delay=random.randint(50, 130))
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await text_inputs.nth(1).click()
            await text_inputs.nth(1).type(last_name, delay=random.randint(50, 130))
        else:
            await _fill_first(page, 'input[type="text"]', full_name)

        await asyncio.sleep(random.uniform(4, 7))

        page_changed = False
        for attempt in range(8):
            print(f"提交姓名 ({attempt + 1}/8)...")
            btn = page.locator('[data-testid="test-primary-button"]').first
            if await btn.is_visible():
                await btn.click()
            await asyncio.sleep(random.uniform(3.5, 5.5))

            body = (await page.content()).lower()
            if "error processing" in body or "try again" in body:
                print("   ⚠️ AWS 返回 processing error，等待后重试...")
                await asyncio.sleep(random.uniform(3, 5))
                continue
            if "verification" in page.url.lower() or "digit" in body or "code" in page.url.lower():
                page_changed = True
                print("   ✅ 进入验证码步骤")
                break

        await page.screenshot(path="screenshot_cloak.png")
        if not page_changed:
            print("⚠️ 姓名页可能未通过，仍尝试收验证码...")

        print("等待验证码邮件...")
        verification_code = wait_for_verification_email(jwt_token)
        password = generate_strong_password()

        if verification_code:
            print(f"验证码: {verification_code}")
            code_sel = 'input[placeholder*="digit"], input[type="text"]'
            await _fill_first(page, code_sel, verification_code)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            for sel in ["button:has-text('Continue')", "button:has-text('Verify')", "button[type='submit']"]:
                if await _click_if_visible(page, sel, 3000):
                    break
            await asyncio.sleep(random.uniform(8, 12))

        pwd_inputs = page.locator('input[type="password"]')
        pwd_count = await pwd_inputs.count()
        if pwd_count >= 1:
            print(f"设置密码 ({pwd_count} 个输入框)...")
            await pwd_inputs.nth(0).type(password, delay=random.randint(40, 100))
            if pwd_count >= 2:
                await pwd_inputs.nth(1).type(password, delay=random.randint(40, 100))
            for sel in [
                "button:has-text('Create AWS Builder ID')",
                "button:has-text('Continue')",
                "button[type='submit']",
            ]:
                if await _click_if_visible(page, sel, 3000):
                    break
            await asyncio.sleep(random.uniform(5, 8))

        await page.screenshot(path="final_cloak.png")
        print(f"最终 URL: {page.url}")
        save_account(email_address, password, full_name, jwt_token)
        print("✅ 流程结束")

    except Exception as e:
        print(f"❌ 错误: {e}")
        try:
            await page.screenshot(path="error_cloak.png")
        except Exception:
            pass
    finally:
        await browser.close()


def run() -> None:
    """同步入口。"""
    asyncio.run(run_cloak_async())


if __name__ == "__main__":
    run()
