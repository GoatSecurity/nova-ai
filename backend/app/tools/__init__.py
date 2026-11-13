from backend.app.tools.registry import tool_registry
from backend.app.tools.system.system_tools import register_system_tools
from backend.app.tools.system.desktop_automation import register_desktop_automation_tools
from backend.app.tools.filesystem.file_tools import register_filesystem_tools
from backend.app.tools.development.dev_tools import register_development_tools
from backend.app.tools.utility.utility_tools import register_utility_tools
from backend.app.tools.utility.rss_tools import register_rss_tools

def init_all_tools():
    register_system_tools()
    register_desktop_automation_tools()
    register_filesystem_tools()
    register_development_tools()
    register_utility_tools()
    register_rss_tools()

init_all_tools()
