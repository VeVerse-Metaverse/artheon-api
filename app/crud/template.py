import typing
import uuid
from typing import List, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, joinedload

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDEntity, EntityBatch, EntityParameterError, EntityAccessError


class CRUDTemplate(CRUDEntity[models.Template, schemas.TemplateCreate, schemas.TemplateUpdate]):
    # Filter out mods without files.
    def index(self, db, *, requester, offset=0, limit=10, filters=None, options=None) -> EntityBatch[models.Template]:
        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index(db, requester=requester, offset=offset, limit=limit, filters=filters, options=options)

    # Filter out mods without files.
    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.Template]:
        if fields is None:
            fields = ['name', 'summary', 'description']

        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    # Filter out mods without files.
    def index_with_query_sorted(self, db, *, requester, offset=0, limit=10, query=None, sort=-1, fields=None, filters=None, options=None) -> EntityBatch[models.Template]:
        if fields is None:
            fields = ['name', 'summary', 'description']

        if not requester.is_admin:
            if isinstance(filters, List):
                filters.append(self.model.files != None)
            else:
                filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query_sorted(db, requester=requester, offset=offset, limit=limit, query=query, sort=sort, fields=fields, filters=filters, options=options)

    def create_for_requester(self, db: Session, *, requester: models.User, source: schemas.TemplateCreate, unique_fields=None) -> models.Template:
        r"""Creates a new entity for the requester."""
        if unique_fields is None:
            unique_fields = []

        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Create a JSON-compatible dict.
        json = jsonable_encoder(source, by_alias=False)

        # Check that required properties are in the dict.
        required = self.get_create_required_fields()
        if not all(el in list(json.keys()) for el in required):
            raise EntityParameterError(f"required properties: {', '.join(required)}")

        if len(json['title']) <= 0:
            raise EntityParameterError(f"title cannot be empty")

        json['name'] = json['title'].translate({ord(c): "" for c in "`-#*/\\%:;?+|\"'><!"})
        json['name'] = "_".join(json['name'].split())
        json['name'] = ''.join([i if ord(i) < 128 else '' for i in json['name']])
        if len(json['name']) > 32:
            raise EntityParameterError(f"name is too long, must be less than or equal to 32 characters")
        if len(json['name']) <= 0 or json['name'] == len(json['name']) * "_":
            raise EntityParameterError(f"name contains invalid characters, please use alphanumeric characters")

        # Create a new entity using source data.
        entity: models.Entity = self.model(**json)

        # Generate a new UUID if required
        if entity.id is None:
            entity.id = uuid.uuid4().hex

        # Check if entity has a name and the name is available.
        for field in unique_fields:
            if field in json:
                if self.check_exists_by_field(db, name=field, value=json[field]):
                    raise EntityParameterError(f"{field} not unique")

        # Create an accessible trait.
        accessible = models.Accessible()
        accessible.entity_id = entity.id
        accessible.user_id = requester.id
        accessible.is_owner = True
        accessible.can_view = True
        accessible.can_edit = True
        accessible.can_delete = True

        # Store the entity and trait in the database.
        db.add(entity)
        db.add(accessible)
        db.commit()
        db.refresh(entity)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.create)

        return entity

    # noinspection PyShadowingNames
    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], patch: Union[schemas.TemplateUpdate, typing.Dict[str, typing.Any]], unique_fields=None):
        if unique_fields is None:
            unique_fields = []

        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, model=self.model, options=joinedload(self.model.accessibles))

        # Ensure that the entity is editable by the requester.
        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        # Create a JSON-compatible dict.
        json = jsonable_encoder(patch, by_alias=False)
        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

        updated_properties: int = 0

        if len(json['title']) <= 0:
            raise EntityParameterError(f"title cannot be empty")

        json['name'] = json['title'].translate({ord(c): "" for c in "`-#*/\\%:;?+|\"'><!"})
        json['name'] = "_".join(json['name'].split())
        json['name'] = ''.join([i if ord(i) < 128 else '' for i in json['name']])
        patch['name'] = json['name']
        if len(json['name']) > 32:
            raise EntityParameterError(f"name is too long, must be less than or equal to 32 characters")
        else:
            if len(json['name']) <= 0 or json['name'] == len(json['name']) * "_":
                raise EntityParameterError(f"name contains invalid characters, please use alphanumeric characters")
            else:
                # Patch the entity with values of the existing fields.
                for field in json:
                    # Do not change id.
                    if field != "id":
                        if field in patch and getattr(entity, field) != patch[field]:
                            setattr(entity, field, patch[field])
                            updated_properties += 1

                # Check if entity has a name and the name is available.
                for field in unique_fields:
                    if field in json:
                        if hasattr(entity, field) and getattr(entity, field) != json[field]:
                            if self.check_exists_by_field(db, name=field, value=json[field]):
                                raise EntityParameterError(f"{field} not unique")

                # Store the entity in the database if it should be updated.
                if updated_properties > 0:
                    db.add(entity)
                    db.commit()
                    db.refresh(entity)

                    crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return entity

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Template.title.name]


template = CRUDTemplate(models.Template)
