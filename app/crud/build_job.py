import logging
import uuid
from typing import List

from sqlalchemy.orm import Session, Query

from app import models, schemas
from app.crud.entity import CRUDBase, EntityParameterError, EntityAccessError

logger = logging.getLogger(__name__)

class CRUDBuildJob(CRUDBase[models.BuildJob, schemas.BuildJob, schemas.BuildJob]):
    def get_pending_job(self, platforms: str, *, db: Session, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        q: Query = db.query(self.model)

        platform_list = platforms.split(',')
        if len(platform_list) > 8:
            raise EntityParameterError('invalid platforms')

        q = q.filter(models.BuildJob.status == 'pending', models.BuildJob.platform.in_(platform_list))

        job = q.first()

        if job:
            # Assign worker
            job.worker_id = requester.id
            job.status = 'processing'
            db.add(job)
            db.commit()
            return job

        return None

    def get_jobs(self, platforms: str, *, db: Session, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not (requester.is_internal or requester.is_admin):
            raise EntityAccessError('access denied')

        q: Query = db.query(self.model)

        platform_list = platforms.split(',')
        if len(platform_list) > 8:
            platform_list = ['Win64', 'Mac', 'Linux', 'IOS', 'Android']

        q = q.filter(models.BuildJob.platform.in_(platform_list))

        jobs = q.all()

        return jobs

    def add_pending_job(self, mod_id: str, configuration: str, map: str, release_name: str, platforms: List[str], *, db: Session, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Allow every user to schedule jobs
        # if not requester.is_internal:
        #     raise EntityAccessError('access denied')

        try:
            uuid.UUID(mod_id)
        except ValueError as e:
            raise EntityParameterError(e)

        mod = db.query(models.Mod).filter(models.Mod.id == mod_id).first()
        if mod is None:
            raise EntityParameterError('mod not found')

        if not map:
            spaces: List[models.Space] = db.query(models.Space).filter(models.Space.mod_id == mod_id).all()
            space_maps = [] 
            for space in spaces:
                space_maps.append(space.map)
            map = "+".join(space_maps)

        logger.info(f"mod: {mod.id}, {mod.name}")
        logger.info(f"maps: {map}")
        logger.info(f"platforms: {platforms}")

        for platform in platforms:
            # Server job, skip building anything except Linux
            if platform not in ['Win64', 'Mac', 'IOS', 'Android']:
                job = models.BuildJob()
                job.id = uuid.uuid4().hex
                job.status = 'pending'
                job.user_id = requester.id
                job.mod_id = mod_id
                job.configuration = configuration
                job.platform = platform
                job.server = True
                job.map = map
                job.release_name = release_name
                logger.info(f"job platform: {platform}, server: true")
                db.add(job)

            # Client job, skip building Linux and mobile platforms
            if platform not in ['Linux', 'IOS', 'Android']:
                job = models.BuildJob()
                job.id = uuid.uuid4().hex
                job.status = 'pending'
                job.user_id = requester.id
                job.mod_id = mod_id
                job.configuration = configuration
                job.platform = platform
                job.server = False
                job.map = map
                job.release_name = release_name
                logger.info(f"job platform: {platform}, server: false")
                db.add(job)
            db.commit()

        return True

    def update_job(self, job_id: str, job_status: str, *, db: Session, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not (requester.is_internal or requester.is_admin):
            raise EntityAccessError('access denied')

        q: Query = db.query(self.model)
        q = q.filter(models.BuildJob.id == job_id)
        job: models.BuildJob = q.first()

        if job is None:
            raise EntityParameterError('job not found')

        if job.worker_id != requester.id and job.status == 'processing':
            raise EntityAccessError('assigned to another worker')

        job.status = job_status
        db.add(job)
        db.commit()

        return job


build_job = CRUDBuildJob(models.BuildJob)
