from uuid import UUID

from sqlalchemy.orm import Session

from app.generators.consistency_checker import check_consistency
from app.models.user import User
from app.services.api_contract_service import ApiContractService
from app.services.blueprint_service import BlueprintService
from app.services.context_pack_service import ContextPackService
from app.services.db_model_service import DbModelService
from app.services.project_service import ProjectService


class ConsistencyService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def check_project_consistency(self, project_id: UUID) -> dict[str, object]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        blueprint = BlueprintService(self.db, self.current_user).get_latest_blueprint(project_id)
        api_contract = ApiContractService(self.db, self.current_user).get_latest_api_contract(
            project_id
        )
        db_model = DbModelService(self.db, self.current_user).get_latest_db_model(project_id)
        roles = ContextPackService(self.db, self.current_user).get_project_roles(project_id)
        return check_consistency(
            blueprint.content if blueprint else None,
            api_contract.content if api_contract else None,
            db_model.content if db_model else None,
            roles,
        )
