import re
import typing
import uuid
from typing import List, Union

import inject
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Query, Session, joinedload, aliased

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDEntity, EntityBatch, EntityParameterError, EntityAccessError
from app.services.image import Service


class CRUDMod(CRUDEntity[models.Mod, schemas.ModCreate, schemas.ModUpdate]):
    imageService = inject.attr(Service)

    # Filter out mods without files.
    def index(self, db, *, requester, offset=0, limit=10, filters=None, options=None) -> EntityBatch[models.Mod]:
        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index(db, requester=requester, offset=offset, limit=limit, filters=filters, options=options)

    # Filter out mods without files.
    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.Object]:
        if fields is None:
            fields = ['name', 'summary', 'description']

        # if isinstance(filters, List):
        #     filters.append(self.model.files != None)
        # else:
        #     filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    # Filter out mods without files.
    def index_with_query_sorted(self, db, *, requester, offset=0, limit=10, query=None, sort=-1, fields=None, filters=None, options=None) -> EntityBatch[models.Object]:
        if fields is None:
            fields = ['name', 'summary', 'description']

        # if not requester.is_admin:
        #     if isinstance(filters, List):
        #         filters.append(self.model.files != None)
        #     else:
        #         filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query_sorted(db, requester=requester, offset=offset, limit=limit, query=query, sort=sort, fields=fields, filters=filters, options=options)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_platforms(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> List[str]:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        entity = self.prepare_entity(db, entity=entity, model=models.Mod)

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Platform).join(models.ModPlatformAssociation)

        q = q.filter(models.ModPlatformAssociation.mod_id == entity.id)

        q = q.order_by(models.Platform.name)

        total = q.count()

        platforms = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Platform](platforms, offset, limit, total)

    def create_for_requester(self, db: Session, *, requester: models.User, source: schemas.ModCreate, unique_fields=None) -> models.Mod:
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
        if len(json['name']) > 64:
            raise EntityParameterError(f"name is too long, must be less than or equal to 64 characters")
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
    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], patch: Union[schemas.ModUpdate, typing.Dict[str, typing.Any]], unique_fields=None):
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

        # json['name'] = json['title'].translate({ord(c): "" for c in "`-#*/\\%:;?+|\"'><!"})
        # json['name'] = "_".join(json['name'].split())
        # json['name'] = ''.join([i if ord(i) < 128 else '' for i in json['name']])
        # patch['name'] = json['name']
        # if len(json['name']) > 32:
        #     raise EntityParameterError(f"name is too long, must be less than or equal to 32 characters")
        # else:
        # if len(json['name']) <= 0 or json['name'] == len(json['name']) * "_":
        #     raise EntityParameterError(f"name contains invalid characters, please use alphanumeric characters")
        # else:
        # Patch the entity with values of the existing fields.
        for field in json:
            # Do not change id.
            if field != "id" and field != "name":
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

    # noinspection PyShadowingNames
    def update_platforms(self, db: Session, *, requester: models.User, entity: Union[str, models.Mod], platforms: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not platforms:
            raise EntityParameterError("no platforms")

        if not re.match("^[ ,]*[a-zA-Z0-9]+(?:[ ,]+[a-zA-Z0-9]+)*[ ,]*$", platforms):
            raise EntityParameterError("platforms must be alphanumeric characters separated with commas")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        platforms = [platform.lower() for platform in platforms.split(',')]
        platforms = set(platforms)
        if "" in platforms:
            platforms.remove("")

        for platform in platforms:
            m_platform: models.Platform = db.query(models.Platform).filter(models.Platform.name == platform).first()
            if not m_platform:
                m_platform = models.Platform(id=uuid.uuid4().hex, name=platform)
                db.add(m_platform)

            # Update values.
            m_association: models.ModPlatformAssociation = db.query(models.ModPlatformAssociation).filter(
                models.ModPlatformAssociation.mod_id == entity.id,
                models.ModPlatformAssociation.platform_id == m_platform.id).first()

            if not m_association:
                m_association = models.ModPlatformAssociation()
                m_association.platform = m_platform
                entity.platforms.append(m_association)

        db.add(entity)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_platform)

        return True

    # noinspection PyShadowingNames
    def delete_platform(self, db: Session, *, requester: models.User, entity: Union[str, models.Mod], platform: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not platform:
            raise EntityParameterError("no platforms")

        if not re.match("^[a-zA-Z0-9]+$", platform):
            raise EntityParameterError("platform can include only alphanumeric characters")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        platform = platform.lower()

        m_platform: models.Platform = db.query(models.Platform).filter(models.Platform.name == platform).first()
        if not m_platform:
            return False

        # Update values.
        m_association: models.ModPlatformAssociation = db.query(models.ModPlatformAssociation).filter(models.ModPlatformAssociation.platform_id == m_platform.id,
                                                                                                      models.ModPlatformAssociation.mod_id == entity.id).first()
        if not m_association:
            return False
        else:
            db.delete(m_association)
            db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.remove_platform)

        return True

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_links(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> List[str]:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        entity = self.prepare_entity(db, entity=entity, model=models.Mod)

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.ModLink).join(models.LinkType)

        q = q.filter(models.ModLink.mod_id == entity.id)

        q = q.order_by(models.LinkType.type)

        total = q.count()

        links = q.offset(offset).limit(limit).all()

        return EntityBatch[models.ModLink](links, offset, limit, total)

    # noinspection PyShadowingNames
    def update_links(self, db, *, requester, entity, links):
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not links:
            raise EntityParameterError("no links")

        if not re.match("^[ ,]*[a-zA-Z0-9]+(?:[ ,]+[a-zA-Z0-9]+)*[ ,]*$", links):
            raise EntityParameterError("links must be alphanumeric characters separated with commas")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        links = [link.lower() for link in links.split(',')]
        links = set(links)
        if "" in links:
            links.remove("")

        for link in links:
            m_link: models.ModLink = db.query(models.ModLink).filter(models.ModLink.url == link).first()
            if not m_link:
                m_link = models.ModLink(id=uuid.uuid4().hex, name=link)
                db.add(m_link)

            # Update values.
            m_association: models.ModLink = db.query(models.ModLink).filter(
                models.ModLink.mod_id == entity.id,
                models.ModLink.link_id == m_link.id).first()

            if not m_association:
                m_association = models.ModLink()
                m_association.link = m_link
                entity.links.append(m_association)

        db.add(entity)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_link)

        return True

    # noinspection PyShadowingNames
    def delete_link(self, db: Session, *, requester: models.User, entity: Union[str, models.Mod], link: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not link:
            raise EntityParameterError("no links")

        if not re.match("^[a-zA-Z0-9]+$", link):
            raise EntityParameterError("link can include only alphanumeric characters")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        link = link.lower()

        m_link: models.ModLink = db.query(models.ModLink).filter(models.ModLink.name == link).first()
        if not m_link:
            return False

        # Update values.
        m_association: models.ModLink = db.query(models.ModLink).filter(models.ModLink.link_id == m_link.id,
                                                                        models.ModLink.mod_id == entity.id).first()
        if not m_association:
            return False
        else:
            db.delete(m_association)
            db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.remove_link)

        return True

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_spaces(self, db: Session, *, requester: models.User, mod: Union[str, models.Mod], offset: int, limit: int) -> EntityBatch[models.Space]:
        if not requester:
            raise EntityParameterError('no requester')

        if not mod:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        mod = self.prepare_entity(db, entity=mod, options=[joinedload(self.model.accessibles)])

        if not mod.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Space)

        q = q.filter(models.Space.mod_id == mod.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.Space.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        q = q.order_by(models.Space.created_at)

        total = self.get_total(q, models.Space.id)

        spaces = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Space](spaces, offset, limit, total)


    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Mod.title.name,
                models.Mod.version.name]


mod = CRUDMod(models.Mod)
