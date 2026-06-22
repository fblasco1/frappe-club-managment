app_name = "club_management"
app_title = "Club Management"
app_publisher = "fblasco1"
app_description = "ERP for Sports Clubs"
app_email = "francisco.o.blasco@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "club_management",
		"logo": "/assets/frappe/images/frappe-framework-logo.svg",
		"title": "Club Management",
		"route": "/desk",
		"has_permission": "club_management.members.permissions_app.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/club_management/css/club_management.css"
app_include_css = "club_management.bundle.css"
app_include_js = "club_management.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/club_management/css/club_management.css"
# web_include_js = "/assets/club_management/js/club_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "club_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "club_management/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "club_management.utils.jinja_methods",
# 	"filters": "club_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "club_management.install.before_install"
after_install = "club_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "club_management.uninstall.before_uninstall"
# after_uninstall = "club_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "club_management.utils.before_app_install"
# after_app_install = "club_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "club_management.utils.before_app_uninstall"
# after_app_uninstall = "club_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "club_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Socio": "club_management.members.permissions.socio_query_conditions",
	"Tutor No Socio": "club_management.members.permissions.tutor_no_socio_query_conditions",
	"Grupo Familiar": "club_management.members.permissions.grupo_familiar_query_conditions",
	"Cargo Socio": "club_management.members.permissions.cargo_socio_query_conditions",
}

has_permission = {
	"Socio": "club_management.members.permissions.socio_has_permission",
	"Tutor No Socio": "club_management.members.permissions.tutor_no_socio_has_permission",
	"Grupo Familiar": "club_management.members.permissions.grupo_familiar_has_permission",
	"Cargo Socio": "club_management.members.permissions.cargo_socio_has_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"club_management.members.jobs.cobranza_periodica.run_generar_deuda_si_corresponde",
		"club_management.members.jobs.cobranza_periodica.run_recargos_si_corresponde",
		"club_management.members.jobs.moroso_automatico.run_evaluar_morosos_si_corresponde",
	],
}

# scheduler_events = {
# 	"all": [
# 		"club_management.tasks.all"
# 	],
# 	"daily": [
# 		"club_management.tasks.daily"
# 	],
# 	"hourly": [
# 		"club_management.tasks.hourly"
# 	],
# 	"weekly": [
# 		"club_management.tasks.weekly"
# 	],
# 	"monthly": [
# 		"club_management.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "club_management.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "club_management.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.doctype.number_card.number_card.get_result": (
		"club_management.integrations.number_card_postgres.get_result"
	),
	"frappe.desk.doctype.number_card.number_card.get_percentage_difference": (
		"club_management.integrations.number_card_postgres.get_percentage_difference"
	),
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "club_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["club_management.utils.before_request"]
# after_request = ["club_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["club_management.utils.before_job"]
# after_job = ["club_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# Login dual (SOC-/TNS- → email). Debe ir en `before_login`, no en
# `auth_hooks`: Frappe v16 llama `auth_hooks` sin argumentos en cada request.
before_login = [
	"club_management.members.auth.dual_login.resolve_login_user",
]

extend_bootinfo = "club_management.boot.extend_bootinfo"

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

