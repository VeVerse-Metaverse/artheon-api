import os
import uuid

import requests
from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.tests_old.base import TestCaseBase, login
from app.tests_old.client import client

expected_properties = ["id", "name", "description", "artist", "date", "type", "medium", "width", "height", "source", "sourceId",
                       "sourceUrl", "license", "copyright", "origin", "location", "credit"]

name = "Test Art Object"
artist = "Test Artist"
date = "1920s"
type = "Painting"
medium = "Oil on Canvas"
width = 176
height = 277
source = "www.testmuseum.org"
source_id = "x366595"
source_url = "https://www.testmuseum.org/art/collection/search/x366595"
license = "CC0"
copyright = "© 2000–2020 The Test Museum of Art. All rights reserved."
origin = "Test Excavation Site"
location = "The Test Museum of Art, Test City, TX"
credit = "Test"
img_preview_url = "https://artheon-objects.s3-eu-west-1.amazonaws.com/0194184f06f94846ba2694f09a99fc44_preview.jpeg"
img_full_url = "https://artheon-objects.s3-eu-west-1.amazonaws.com/0194184f06f94846ba2694f09a99fc44_full.jpeg"
img_texture_url = "https://artheon-objects.s3-eu-west-1.amazonaws.com/0194184f06f94846ba2694f09a99fc44.jpeg"


def create_test_object(db: Session) -> models.Object:
    object = schemas.ObjectCreate(name=name, artist=artist, description=name, date=date,
                                  type=type, medium=medium, width=width, height=height, source=source, source_id=source_id,
                                  source_url=source_url, license=license, copyright=copyright, origin=origin, location=location, credit=credit,
                                  img_preview_url=img_preview_url, img_full_url=img_full_url, img_texture_url=img_texture_url)
    return crud.object.create(db, entity=object)


def delete_test_object(db: Session, id) -> None:
    db.query(models.Object).filter(models.Object.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


class ObjectTestCase(TestCaseBase):
    db: Session
    object: models.Object

    @classmethod
    def setUpClass(cls) -> None:
        super(ObjectTestCase, cls).setUpClass()
        login()
        cls.object = create_test_object(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        super(ObjectTestCase, cls).tearDownClass()
        delete_test_object(cls.db, cls.object.id)

    def create_object(self):
        response = client.post("/objects/", json=dict(name=name, artist=artist, description=name, date=date,
                                                      type=type, medium=medium, width=width, height=height, source=source, source_id=source_id,
                                                      source_url=source_url, license=license, copyright=copyright, origin=origin, location=location, credit=credit,
                                                      img_preview_url=img_preview_url, img_full_url=img_full_url, img_texture_url=img_texture_url))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["name"], name)
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)
        return data

    def test_read_all(self):
        self.should("read all objects")
        m_object = create_test_object(self.db)
        response = client.get("/objects/")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        delete_test_object(self.db, m_object.id)
        self.assertGreater(len(data), 0)

    def test_read_query(self):
        self.should("get objects with query")
        m_object = create_test_object(self.db)
        response = client.get("/objects/query?query=test")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        delete_test_object(self.db, m_object.id)
        self.assertGreater(len(data), 0)

    def test_read_search(self):
        self.should("get objects with query")
        m_object = create_test_object(self.db)
        response = client.get("/objects/search?name=test")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        delete_test_object(self.db, m_object.id)
        self.assertGreater(len(data), 0)

    def test_read_similar(self):
        self.should("get similar objects")
        m_object = create_test_object(self.db)
        response = client.get(f"/objects/{self.object.id}/similar")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        delete_test_object(self.db, m_object.id)
        self.assertGreater(len(data), 0)

    def test_read_one(self):
        self.should("get an object")
        response = client.get(f"/objects/{self.object.id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))

    def test_create(self):
        self.should("create a new object")
        data = self.create_object()
        delete_test_object(self.db, data["id"])

    def test_update_non_existent(self):
        self.should("not be able to update non-existent object")
        response = client.patch(f"/objects/non-existent", json=dict(name="new"))
        self.assertEqual(response.status_code, 404, response.text)

    def test_update_not_owned(self):
        self.should("not be able to update not owned object")
        new_name = "New Object"
        response = client.patch(f"/objects/{self.object.id}", json=dict(name=new_name))
        self.assertEqual(response.status_code, 403, response.text)

    def test_update_owned(self):
        self.should("change object name")
        new_name = "New Object Title"
        data = self.create_object()
        response = client.patch(f"/objects/{data['id']}", json=dict(name=new_name, description=new_name))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["name"], new_name)
        self.assertEqual(data["description"], new_name)
        delete_test_object(self.db, data["id"])

    def test_upload_image_non_existent(self):
        file_type = "image_full"
        self.should("upload image for the object")
        with open(f"{os.path.dirname(os.path.realpath(__file__))}/../assets/test.jpeg", "rb") as fp:
            response = client.post(f"/uploads/non-existent/{file_type}", data=dict(id=uuid.uuid4().hex), files={"file": ("filename", fp, "image/jpeg")})
        self.assertEqual(response.status_code, 404, response.text)

    def test_upload_image_not_owned(self):
        file_type = "image_full"
        self.should("upload image for the object")
        with open(f"{os.path.dirname(os.path.realpath(__file__))}/../assets/test.jpeg", "rb") as fp:
            response = client.post(f"/uploads/{self.object.id}/{file_type}", data=dict(id=uuid.uuid4().hex), files={"file": ("filename", fp, "image/jpeg")})
        self.assertEqual(response.status_code, 403, response.text)

    def test_upload_image(self):
        data = self.create_object()

        file_type = "image_full"

        self.should("upload image for the object")
        with open(f"{os.path.dirname(os.path.realpath(__file__))}/../assets/test.jpeg", "rb") as fp:
            response = client.post(f"/uploads/{data['id']}/{file_type}", data=dict(id=uuid.uuid4().hex), files={"file": ("filename", fp, "image/jpeg")})
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertIsNotNone(data)

        self.should("delete object images")
        response = client.delete(f"/uploads/{data['id']}/{file_type}")
        self.assertEqual(response.status_code, 200, response.text)

        self.should("ensure that images were deleted")
        for x in data["files"]:
            response = requests.get(x["url"])
            self.assertEqual(response.status_code, 403, response.text)

        delete_test_object(self.db, data["id"])

    def test_delete_not_owned(self):
        self.should("delete a not owned object")
        response = client.delete(f"/objects/{self.object.id}")
        self.assertEqual(response.status_code, 403, response.text)

    def test_delete_non_existent(self):
        self.should("delete a non-existent object")
        response = client.delete(f"/objects/non-existent")
        self.assertEqual(response.status_code, 404, response.text)

    def test_delete_image_not_owned(self):
        file_type = "image_full"
        self.should("delete a not owned object images")
        response = client.delete(f"/uploads/{self.object.id}/{file_type}")
        self.assertEqual(response.status_code, 403, response.text)

    def test_delete_image_non_existent(self):
        file_type = "image_full"
        self.should("delete a non-existent object images")
        response = client.delete(f"/uploads/non-existent/{file_type}")
        self.assertEqual(response.status_code, 404, response.text)

    def test_delete(self):
        self.should("delete an owned object")
        data = self.create_object()
        response = client.delete(f"/objects/{data['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        response = client.get(f"/objects/{data['id']}")
        self.assertEqual(response.status_code, 404, response.text)
