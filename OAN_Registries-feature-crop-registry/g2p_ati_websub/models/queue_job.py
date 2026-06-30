import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class QueueJobATIWebSub(models.Model):
    _inherit = "queue.job"

    _ATI_WEBSUB_STALE_MINUTES = 10
    _ATI_WEBSUB_MODEL_NAME = "g2p.datashare.config.websub"
    _ATI_WEBSUB_METHOD_NAMES = (
        "publish_event_internal",
        "_publish_consent_payload_job",
    )

    @api.model
    def _ati_websub_stale_domain(self, stale_minutes=None):
        stale_minutes = stale_minutes or self._ATI_WEBSUB_STALE_MINUTES
        deadline = fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(minutes=stale_minutes)
        )
        target_domain = [
            ("model_name", "=", self._ATI_WEBSUB_MODEL_NAME),
            ("method_name", "in", list(self._ATI_WEBSUB_METHOD_NAMES)),
            ("state", "in", ["pending", "enqueued", "started"]),
        ]
        stale_state_domain = expression.OR(
            [
                [("state", "=", "pending"), ("date_created", "<=", deadline)],
                [("state", "=", "enqueued"), ("date_enqueued", "<=", deadline)],
                [("state", "=", "started"), ("date_started", "<=", deadline)],
            ]
        )
        return expression.AND([target_domain, stale_state_domain])

    @api.model
    def fail_stale_ati_websub_jobs(self, stale_minutes=None):
        stale_minutes = stale_minutes or self._ATI_WEBSUB_STALE_MINUTES
        stale_jobs = self.search(self._ati_websub_stale_domain(stale_minutes=stale_minutes))
        if not stale_jobs:
            return True

        completed_at = fields.Datetime.now()
        exc_name = "odoo.addons.g2p_ati_websub.job.StaleWebSubJobError"
        for job in stale_jobs:
            original_state = job.state
            if original_state == "started":
                reference_time = job.date_started
            elif original_state == "enqueued":
                reference_time = job.date_enqueued
            else:
                reference_time = job.date_created
            exc_message = _(
                "ATI WebSub datashare job timed out after more than %(minutes)s minutes "
                "while still in state '%(state)s'."
            ) % {
                "minutes": stale_minutes,
                "state": original_state,
            }
            result = _(
                "Marked failed by ATI WebSub stale-job guard. "
                "Job exceeded %(minutes)s minutes in queue state '%(state)s'."
            ) % {
                "minutes": stale_minutes,
                "state": original_state,
            }
            job.write(
                {
                    "state": "failed",
                    "date_done": completed_at,
                    "worker_pid": False,
                    "exc_name": exc_name,
                    "exc_message": exc_message,
                    "exc_info": exc_message,
                    "result": result,
                }
            )
            _logger.warning(
                "ATI WebSub - Marked stale queue job failed uuid=%s state=%s model=%s method=%s "
                "date_created=%s date_enqueued=%s date_started=%s reference_time=%s timeout_minutes=%s",
                job.uuid,
                original_state,
                job.model_name,
                job.method_name,
                job.date_created,
                job.date_enqueued,
                job.date_started,
                reference_time,
                stale_minutes,
            )
        return True
