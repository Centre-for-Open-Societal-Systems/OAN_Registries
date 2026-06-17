import re

path = 'views/portal_consent_management_hierarchy_templates.xml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace the xpath that targets portal_management_section_anchor
# with two xpaths targeting portal_roles_section_anchor and portal_users_section_anchor.

# First, let's extract the styles
style_match = re.search(r'(<style>.*?</style>)', content, re.DOTALL)
styles = style_match.group(1)

# The content of Roles tab: (We will just keep the table and add a header)
# We can find the roles panel and users panel.
roles_panel_match = re.search(r'<div\s+id="portal_roles_inner_panel"[^>]*>(.*?)</div>\s*<div\s+id="portal_users_inner_panel"', content, re.DOTALL)
roles_content = roles_panel_match.group(1).strip()

users_panel_match = re.search(r'<div\s+id="portal_users_inner_panel"[^>]*>(.*?)</div>\s*</div>\s*<div class="modal fade consent_mgmt_modal" id="create_role_modal"', content, re.DOTALL)
users_content = users_panel_match.group(1).strip()

# Now extract all the modals and foreach loops at the end of the xpath.
modals_match = re.search(r'(<div class="modal fade consent_mgmt_modal" id="create_role_modal".*?</t>\s*</div>\s*</t>\s*</xpath>)', content, re.DOTALL)
modals_content = modals_match.group(1)

# Remove the </t> </div> </t> </xpath> at the end of modals_content
modals_content = re.sub(r'</div>\s*</t>\s*</xpath>$', '', modals_content, flags=re.DOTALL).strip()

new_xpath_roles = f"""
        <xpath expr="//div[@id='portal_roles_section_anchor']" position="replace">
            <t t-if="portal_management_enabled">
                <div class="mb-4">
                    {styles}
                    {roles_content}
                </div>
            </t>
        </xpath>
"""

new_xpath_users = f"""
        <xpath expr="//div[@id='portal_users_section_anchor']" position="replace">
            <t t-if="portal_management_enabled">
                <div class="mb-4">
                    {users_content}
                    {modals_content}
                </div>
            </t>
        </xpath>
"""

# The original block starts with <xpath expr="//div[@id='portal_management_section_anchor']" position="replace">
old_xpath_match = re.search(r'<xpath expr="//div\[@id=\'portal_management_section_anchor\'\]" position="replace">.*?</xpath>', content, re.DOTALL)

new_content = content.replace(old_xpath_match.group(0), new_xpath_roles.strip() + "\n" + new_xpath_users.strip())

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

