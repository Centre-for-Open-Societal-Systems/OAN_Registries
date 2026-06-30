from odoo.addons.g2p_registry_rest_api.schemas import individual


class UpdateIndividualInfoRequest(
    individual.UpdateIndividualInfoRequest, extends=individual.UpdateIndividualInfoRequest
):
    gf_name_eng: str | None
    first_name_amh: str | None
    family_name_amh: str | None
    gf_name_amh: str | None


class UpdateIndividualInfoResponse(
    individual.UpdateIndividualInfoResponse, extends=individual.UpdateIndividualInfoResponse
):
    gf_name_eng: str | None = None
    first_name_amh: str | None = None
    family_name_amh: str | None = None
    gf_name_amh: str | None = None
