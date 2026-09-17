const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:8000';
const OUT = '/home/claude/zoomart-approval/screenshots';

async function login(browser, username) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  await page.goto(BASE + '/login/');
  await page.fill('input[name=username]', username);
  await page.fill('input[name=password]', 'Zoomart2026!');
  await page.click('button[type=submit]');
  await page.waitForLoadState('networkidle');
  return page;
}

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });

  // Login page
  const anonCtx = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  let page = await anonCtx.newPage();
  await page.goto(BASE + '/login/');
  await page.screenshot({ path: `${OUT}/01_login.png` });
  await page.close();

  // Employee dashboard
  page = await login(browser, 'employee1');
  await page.screenshot({ path: `${OUT}/02_employee_dashboard.png`, fullPage: true });

  // New request form
  await page.goto(BASE + '/requests/new/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/03_new_request_form.png`, fullPage: true });

  // My requests list
  await page.goto(BASE + '/requests/?scope=mine');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/04_my_requests_list.png`, fullPage: true });
  await page.close();

  // Manager dashboard + approval action panel
  page = await login(browser, 'it.manager');
  await page.screenshot({ path: `${OUT}/05_manager_dashboard.png`, fullPage: true });
  await page.goto(BASE + '/requests/5/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/06_request_detail_more_info.png`, fullPage: true });
  await page.close();

  // Full timeline example (r6: submitted -> approved -> approved -> rejected)
  page = await login(browser, 'director');
  await page.goto(BASE + '/requests/6/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/07_request_detail_timeline.png`, fullPage: true });

  // Management dashboard
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/08_management_dashboard.png`, fullPage: true });
  await page.close();

  // Finance dashboard + queue
  page = await login(browser, 'finance');
  await page.screenshot({ path: `${OUT}/09_finance_dashboard.png`, fullPage: true });
  await page.goto(BASE + '/requests/?scope=finance');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/10_finance_queue.png`, fullPage: true });
  await page.close();

  // Admin panel
  page = await login(browser, 'admin');
  await page.goto(BASE + '/admin/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/11_admin_panel.png`, fullPage: true });
  await page.goto(BASE + '/admin/core/approvalworkflowrule/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${OUT}/12_admin_approval_rules.png`, fullPage: true });
  await page.close();

  await browser.close();
  console.log('done');
})();
