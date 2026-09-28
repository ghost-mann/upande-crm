"""Which whitelisted endpoints each module switch gates.

Data, not tests: `test_modules.TestEnforcement` walks this map, and every entry
must carry `@requires_module(<key>)`. Endpoints shared across sections
(`crm_assign`, `crm_search`, the `advance` hops, `crm_sales_analytics`, which the
Overview reads, `crm_call_types`, which the call dialog reads from anywhere)
are deliberately absent.
"""

GATED = {
    "customer_page": [
        "upande_crm.api.customer.crm_customer_header",
        "upande_crm.api.customer.crm_customer_overview",
        "upande_crm.api.customer.crm_customer_orders",
        "upande_crm.api.customer.crm_customer_pricing",
        "upande_crm.api.customer.crm_customer_contracts",
        "upande_crm.api.customer.crm_customer_timeline",
        "upande_crm.api.customer.crm_customer_add_note",
    ],
    "leads": ["upande_crm.api.crm.crm_dashboard_leads", "upande_crm.api.leads.crm_lead_save"],
    "opps": ["upande_crm.api.crm.crm_dashboard_opportunities"],
    "prosp": ["upande_crm.api.crm.crm_dashboard_prospects"],
    "mail": [
        "upande_crm.api.crm.crm_mail_data",
        "upande_crm.api.crm.crm_mark_read",
        "upande_crm.api.crm.crm_send_email",
    ],
    "wa": [
        "upande_crm.api.whatsapp.crm_whatsapp_conversations",
        "upande_crm.api.whatsapp.crm_whatsapp_thread",
        "upande_crm.api.whatsapp.crm_whatsapp_send",
        "upande_crm.api.whatsapp.crm_whatsapp_send_template",
        "upande_crm.api.whatsapp.crm_whatsapp_templates",
        "upande_crm.api.whatsapp.crm_whatsapp_analytics",
        "upande_crm.api.whatsapp.crm_whatsapp_mark_read",
        "upande_crm.api.whatsapp.crm_whatsapp_match",
    ],
    "calls": [
        "upande_crm.api.calls.crm_dashboard_calls",
        "upande_crm.api.calls.crm_call_save",
        "upande_crm.api.calls.crm_call_delete",
        "upande_crm.api.calls.crm_call_type_add",
    ],
    "evt": [
        "upande_crm.api.crm.crm_dashboard_events_tasks",
        "upande_crm.api.activity.crm_calendar",
        "upande_crm.api.activity.crm_my_calendars",
        "upande_crm.api.activity.crm_event_save",
        "upande_crm.api.activity.crm_event_status",
        "upande_crm.api.activity.crm_task_save",
        "upande_crm.api.activity.crm_task_status",
    ],
    "act": ["upande_crm.api.crm.crm_dashboard_activity"],
    "camp": [
        "upande_crm.api.campaigns.crm_dashboard_campaigns",
        "upande_crm.api.campaigns.crm_campaign_detail",
        "upande_crm.api.campaigns.crm_campaign_save",
        "upande_crm.api.campaigns.crm_campaign_enrol",
        "upande_crm.api.campaigns.crm_campaign_cancel",
        "upande_crm.api.campaigns.crm_campaign_recipients",
    ],
    "anl": [
        "upande_crm.api.pipeline.crm_analytics_funnel",
        "upande_crm.api.pipeline.crm_analytics_leads",
        "upande_crm.api.pipeline.crm_analytics_opportunities",
        "upande_crm.api.pipeline.crm_analytics_revenue",
    ],
    "rep": [
        "upande_crm.api.reports.crm_reports",
        "upande_crm.api.reports.crm_report_run",
        "upande_crm.api.reports.crm_report_catalogue",
    ],
    "terr": [
        "upande_crm.api.territory.crm_territory_map",
        "upande_crm.api.territory.crm_territory_detail",
        "upande_crm.api.logistics.crm_delivery_points",
        "upande_crm.api.logistics.crm_delivery_point_detail",
    ],
    "corr": ["upande_crm.api.correspondence.crm_correspondence"],
}
