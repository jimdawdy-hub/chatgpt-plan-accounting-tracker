const fmt = {
  num: n => Number(n || 0).toLocaleString(undefined, {maximumFractionDigits: 0}),
  credits: n => Number(n || 0).toLocaleString(undefined, {maximumFractionDigits: 2}),
  pct: n => `${(Number(n || 0) * 100).toFixed(1)}%`,
};

const charts = {};
let latestSummary = null;

function chart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

async function getJson(path) {
  const res = await fetch(path);
  return res.json();
}

async function syncReports() {
  const btn = document.getElementById("syncBtn");
  btn.disabled = true;
  btn.textContent = "Syncing...";
  try {
    await fetch("/api/sync", {method: "POST"});
    await loadAll();
  } finally {
    btn.disabled = false;
    btn.textContent = "Sync Reports";
  }
}

async function loadSummary() {
  const data = await getJson("/api/summary");
  latestSummary = data;
  const totals = data.totals || {};
  const billing = data.billing || {};

  document.getElementById("codexCredits").textContent = fmt.credits(totals.codex_credits);
  document.getElementById("codexDollarValue").textContent =
    `${money(Number(totals.codex_credits || 0) * Number(data.credit_usd_rate || 0))} dollar equivalent`;
  document.getElementById("billableCredits").textContent = fmt.credits(billing.billable_credits);
  document.getElementById("sessionsTurns").textContent = `${fmt.num(totals.threads)} / ${fmt.num(totals.turns)}`;
  document.getElementById("cacheRatio").textContent = fmt.pct(data.cache_ratio);
  document.getElementById("billableEvents").textContent = `${fmt.num(billing.events)} purchase/usage entries found in the exported credit report.`;
  document.getElementById("dateRange").textContent =
    `Imported Codex report dates: ${data.date_range?.start || "-"} to ${data.date_range?.end || "-"}. Dollar equivalent uses ${money(data.credit_usd_rate)} per credit.`;
  document.getElementById("rateCardLink").href = data.rate_card_url;
  document.getElementById("pricingLink").href = data.chatgpt_pricing_url;
  renderPlanSelect(data.plans || {}, data.active_plan);
  renderPlanSettings(data);
  renderPlanValue(data.plan_value || {});
  renderProjection(data.projection || {});
  renderPlainEnglish(data);

  const gap = Number(data.visible_gap || 0);
  const billable = Number(billing.billable_credits || 0);
  const internal = Number(totals.codex_credits || 0);
  document.getElementById("reconciliation").textContent =
    `The Codex telemetry ledger shows ${fmt.credits(internal)} internal credits. ` +
    `The credit usage report shows ${fmt.credits(billable)} visible billable credits. ` +
    `The remaining ${fmt.credits(gap)} credits are internal telemetry, included-plan usage, ` +
    `workspace allocation, or unexported billing categories until a matching billable event appears.`;

  renderPlanRows(data.plan_costs || {}, data.active_plan, data.projection || {});
}

function renderPlainEnglish(data) {
  const el = document.getElementById("plainEnglishBreakdown");
  const projection = data.projection || {};
  const planValue = data.plan_value || {};
  const totalApiProjection = window.latestModelApiProjection || null;
  const apiSavings = totalApiProjection == null || projection.selected_plan_cost_usd == null
    ? null
    : totalApiProjection - projection.selected_plan_cost_usd;

  el.innerHTML = `
    <p><strong>1. What the data means.</strong> The Codex reports show how much model work happened: sessions, messages, models, and token buckets. The credit CSV shows extra purchased-credit events. These are different ledgers, so the dashboard keeps them separate.</p>
    <p><strong>2. Plan vs. API savings.</strong> Based on direct API token pricing, your current pace projects to about <strong>${money(totalApiProjection)}</strong> in API tokens over 30 days. Your selected plan base cost is <strong>${money(projection.selected_plan_cost_usd)}</strong>, so the estimated 30-day savings versus pure API token billing is <strong>${signedMoney(apiSavings)}</strong>.</p>
    <p><strong>3. Cost buckets.</strong> Direct API token equivalent is the raw model-token price. Codex internal credits are OpenAI's Codex usage meter. Additional purchased credits are extra credits used outside the included plan. Plan cost is the monthly subscription cost, currently <strong>${money(planValue.base_monthly_usd)}</strong> for ${planValue.label || "the selected plan"}.</p>
    <p><strong>4. Why subscriptions can work this way.</strong> The simple analogy is a gym membership: lighter users pay every month and use little capacity, while heavy users get a lot of value. Providers accept that tradeoff to grow adoption, keep users in the product, and average costs across many usage patterns.</p>
  `;
}

function money(n) {
  return n == null ? "Custom" : `$${Number(n).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
}

function signedMoney(n) {
  if (n == null) return "Custom";
  const value = Number(n);
  return `${value >= 0 ? "+" : "-"}$${Math.abs(value).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
}

function renderPlanValue(value) {
  const main = document.getElementById("netPlanValue");
  const sub = document.getElementById("netPlanValueSub");
  main.textContent = signedMoney(value.net_value_usd);
  main.classList.toggle("negative", Number(value.net_value_usd || 0) < 0);
  if (value.net_value_usd == null) {
    sub.textContent = `${value.label || "Enterprise"} has custom base pricing`;
    return;
  }
  sub.textContent =
    `${money(value.usage_value_usd)} internal value - ${money(value.base_monthly_usd)} plan - ${money(value.visible_extra_cost_usd)} visible credits`;
}

function renderPlanSelect(plans, activePlan) {
  const select = document.getElementById("planSelect");
  const currentOptions = Array.from(select.options).map(o => o.value).join("|");
  const nextOptions = Object.keys(plans).join("|");
  if (currentOptions !== nextOptions) {
    select.innerHTML = "";
    Object.entries(plans).forEach(([key, plan]) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = plan.label;
      select.appendChild(opt);
    });
  }
  select.value = activePlan || "Business";
}

function renderPlanSettings(data) {
  const start = document.getElementById("planStartDate");
  const seats = document.getElementById("seatCount");
  if (document.activeElement !== start) start.value = data.plan_start_date || "";
  if (document.activeElement !== seats) seats.value = data.seat_count || 2;
}

function renderProjection(projection) {
  const el = document.getElementById("projectionText");
  if (!projection.projected_30d_usage_value_usd) {
    el.textContent = "Set your plan start date to project your plan value.";
    return;
  }
  el.textContent =
    `Since ${projection.start_date}, usage is tracking at ${fmt.credits(projection.daily_credit_rate)} credits/day. ` +
    `Projected over 30 days: ${fmt.credits(projection.projected_30d_credits)} credits, worth ${money(projection.projected_30d_usage_value_usd)}. ` +
    `Against your selected plan cost of ${money(projection.selected_plan_cost_usd)}, projected plan value is ${signedMoney(projection.selected_plan_projected_savings_usd)}.`;
}

function baseRateLabel(plan) {
  if (plan.base_monthly_usd == null) return "Custom pricing";
  if (plan.annual_monthly_usd != null) {
    return `${money(plan.annual_monthly_usd)} annual / ${money(plan.base_monthly_usd)} monthly per user`;
  }
  if (plan.billing_unit === "workspace") return `${money(plan.base_monthly_usd)} fixed seat fee`;
  return `${money(plan.base_monthly_usd)} / ${plan.billing_unit || "month"}`;
}

function totalRateLabel(plan) {
  if (plan.monthly_total_with_visible_credits == null) return "Custom + visible credits";
  if (plan.annual_monthly_total_with_visible_credits != null) {
    return `${money(plan.annual_monthly_total_with_visible_credits)} annual basis / ${money(plan.monthly_total_with_visible_credits)} monthly basis`;
  }
  return `${money(plan.monthly_total_with_visible_credits)}`;
}

function renderPlanRows(plans, activePlan, projection) {
  const selectedBody = document.getElementById("selectedPlanRows");
  const tbody = document.getElementById("planRows");
  selectedBody.innerHTML = "";
  tbody.innerHTML = "";
  Object.entries(plans).forEach(([key, plan]) => {
    const comparison = projection.comparisons?.[key] || {};
    const projected = comparison.projected_savings_usd;
    const finalCell = key === activePlan ? signedMoney(projected) : (comparison.comparison_note || "Not comparable without plan limit data");
    const html = `
      <tr>
        <td>${plan.label}</td>
        <td>${baseRateLabel(plan)}</td>
        <td>${key === activePlan ? totalRateLabel(plan) : (comparison.codex_access || "Unknown")}</td>
        <td>${finalCell}</td>
      </tr>
    `;
    if (key === activePlan) selectedBody.insertAdjacentHTML("beforeend", html);
    else {
      tbody.insertAdjacentHTML("beforeend", `
        <tr>
          <td>${plan.label}</td>
          <td>${baseRateLabel(plan)}</td>
          <td>${comparison.codex_access || "Unknown"}</td>
          <td>${comparison.limit_policy || "No public numeric quota"}</td>
          <td>${finalCell}</td>
        </tr>
      `);
    }
  });
}

async function loadDaily() {
  const rows = await getJson("/api/daily");
  chart("dailyChart", {
    type: "bar",
    data: {
      labels: rows.map(r => r.date.slice(5)),
      datasets: [
        {label: "Internal Codex credits", data: rows.map(r => r.credits), backgroundColor: "#3178c6"},
        {label: "On-demand credits", data: rows.map(r => r.on_demand_credits), backgroundColor: "#d95f59"},
      ],
    },
    options: {responsive: true, scales: {y: {beginAtZero: true}}},
  });
}

async function loadModels() {
  const rows = await getJson("/api/models");
  const tbody = document.getElementById("modelRows");
  const apiBody = document.getElementById("apiCostRows");
  tbody.innerHTML = "";
  apiBody.innerHTML = "";
  rows.forEach(row => {
    tbody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${row.model}</td>
        <td>${fmt.credits(row.credits)}</td>
        <td>${fmt.credits(row.estimated_credits)}</td>
        <td>${fmt.num(row.total_tokens)}</td>
      </tr>
    `);
    const rates = row.api_rates
      ? `rates: ${money(row.api_rates.input)}/M input, ${money(row.api_rates.cached_input)}/M cached, ${money(row.api_rates.output)}/M output`
      : "no API pricing configured";
    apiBody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${row.model}<div class="muted-cell">${rates}</div></td>
        <td>${money(row.api_input_cost_usd)}<div class="muted-cell">${fmt.num(row.uncached)} tokens</div></td>
        <td>${money(row.api_cached_cost_usd)}<div class="muted-cell">${fmt.num(row.cached)} tokens</div></td>
        <td>${money(row.api_output_cost_usd)}<div class="muted-cell">${fmt.num(row.output)} tokens</div></td>
        <td><strong>${money(row.api_total_cost_usd)}</strong></td>
        <td><strong>${signedMoney(row.api_projected_30d_savings_vs_plan_usd)}</strong><div class="muted-cell">30-day API projection ${money(row.api_projected_30d_cost_usd)} minus allocated plan cost ${money(row.selected_plan_cost_share_usd)}</div></td>
      </tr>
    `);
  });
  window.latestModelApiProjection = rows.reduce((sum, row) => sum + Number(row.api_projected_30d_cost_usd || 0), 0);
  if (latestSummary) renderPlainEnglish(latestSummary);

  chart("modelChart", {
    type: "doughnut",
    data: {
      labels: rows.map(r => r.model),
      datasets: [{data: rows.map(r => r.credits), backgroundColor: ["#3178c6", "#6aa84f", "#f2b84b", "#8e6ccf", "#d95f59"]}],
    },
    options: {responsive: true},
  });
}

async function loadClients() {
  const rows = await getJson("/api/clients");
  const tbody = document.getElementById("clientRows");
  tbody.innerHTML = "";
  rows.forEach(row => {
    tbody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${row.client_id}</td>
        <td>${fmt.num(row.threads)}</td>
        <td>${fmt.num(row.turns)}</td>
        <td>${fmt.credits(row.credits)}</td>
      </tr>
    `);
  });
}

async function loadCreditEvents() {
  const rows = await getJson("/api/credit-events");
  const tbody = document.getElementById("creditRows");
  tbody.innerHTML = "";
  rows.forEach(row => {
    tbody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${row.date}</td>
        <td>${row.seat_type}</td>
        <td>${row.usage_type}</td>
        <td>${fmt.credits(row.usage_quantity)}</td>
        <td>${fmt.credits(row.usage_credits)}</td>
      </tr>
    `);
  });
}

async function loadAll() {
  await Promise.all([loadSummary(), loadDaily(), loadModels(), loadClients(), loadCreditEvents()]);
}

document.getElementById("syncBtn").addEventListener("click", syncReports);
document.getElementById("planSelect").addEventListener("change", async event => {
  await fetch("/api/plan", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({plan: event.target.value}),
  });
  await loadAll();
});
async function saveSettings() {
  await fetch("/api/settings", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      plan_start_date: document.getElementById("planStartDate").value,
      seat_count: document.getElementById("seatCount").value,
    }),
  });
  await loadAll();
}
document.getElementById("planStartDate").addEventListener("change", saveSettings);
document.getElementById("seatCount").addEventListener("change", saveSettings);
loadAll();
