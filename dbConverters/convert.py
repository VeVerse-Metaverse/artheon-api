from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

import app.database as database
import app.models as newmodels
import parsers.database as olddatabase
import parsers.models as oldmodels


def object_as_dict(obj):
    return {c.key: getattr(obj, c.key)
            for c in inspect(obj).mapper.column_attrs}


def process_objects():
    with olddatabase.session() as oldDB:
        newDB = database.SessionLocal()
        # Batches count.
        count = 1000  # 1000
        limit = 100  # 100

        # For each batch
        for page in range(count):
            objects = oldDB.query(oldmodels.Object).offset(page * limit).limit(limit).all()

            for object in objects:
                o = newmodels.Object()
                o.id = object.id
                o.artist = object.artist
                o.medium = object.medium
                o.type = object.type
                o.copyright = object.copyright
                o.created_at = object.created_at
                o.credit = object.credit
                o.date = object.date
                o.description = object.description
                o.entity_type = 'object'
                o.height = object.height
                o.width = object.width
                o.license = object.license
                o.location = object.location
                o.origin = object.origin
                o.source = object.source
                o.public = True
                o.source_id = object.source_id
                o.source_url = object.source_url
                o.title = object.name
                o.tags = object.tags
                newDB.add(o)

                # For each object create files.
                if object.image_full_url:
                    f_full = newmodels.File()
                    f_full.entity_id = o.id
                    f_full.created_at = object.created_at
                    f_full.type = 'image_full'
                    f_full.url = object.image_full_url
                    f_full.mime = 'image/jpeg'
                    newDB.add(f_full)

                if object.image_preview_url:
                    f_preview = newmodels.File()
                    f_preview.entity_id = o.id
                    f_preview.created_at = object.created_at
                    f_preview.type = 'image_preview'
                    f_preview.url = object.image_preview_url
                    f_preview.mime = 'image/jpeg'
                    newDB.add(f_preview)

                if object.image_texture_url:
                    f_texture = newmodels.File()
                    f_texture.entity_id = o.id
                    f_texture.created_at = object.created_at
                    f_texture.type = 'texture_diffuse'
                    f_texture.url = object.image_texture_url
                    f_texture.mime = 'image/jpeg'
                    newDB.add(f_texture)

                a = newmodels.Accessible()
                a.entity_id = o.id
                a.user_id = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
                a.is_owner = True
                a.can_view = True
                a.can_edit = True
                a.can_delete = True
                newDB.add(a)

                a = newmodels.Accessible()
                a.entity_id = o.id
                a.user_id = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
                a.is_owner = True
                a.can_view = True
                a.can_edit = True
                a.can_delete = True
                newDB.add(a)

                try:
                    newDB.commit()
                except IntegrityError as err:
                    print(err)
                    newDB.rollback()

        newDB.close()
    # For each object create entity.
    # For each object create metObject.
    # For each object create log.


def process():
    # For each collection create entity.
    # For each object create entity.
    # For each met object create metObject.
    # For each object having files create files.
    # For each object create log.
    process_objects()


if __name__ == '__main__':
    process()
