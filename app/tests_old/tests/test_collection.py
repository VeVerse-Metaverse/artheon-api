from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.tests_old.base import TestCaseBase, login
from app.tests_old.client import client

expected_properties = ["id", "name", "description"]


def create_test_collection(db: Session) -> models.Collection:
    collection = schemas.CollectionCreate(name="Test Collection", description="Test Collection")
    return crud.collection.create(db, entity=collection)


def delete_test_collection(db: Session, id) -> None:
    db.query(models.Collection).filter(models.Collection.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


class CollectionTestCase(TestCaseBase):
    db: Session
    collection: models.Collection

    @classmethod
    def setUpClass(cls) -> None:
        super(CollectionTestCase, cls).setUpClass()
        login()
        cls.collection = create_test_collection(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        super(CollectionTestCase, cls).tearDownClass()
        delete_test_collection(cls.db, cls.collection.id)

    def test_read_all(self):
        self.should("get a list of more than 0 collections")
        response = client.get("/collections/")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertGreater(len(data), 0)

    def test_read_non_existent(self):
        self.should("get error reading non-existent collection")
        response = client.get(f"/collections/non-existent")
        self.assertEqual(response.status_code, 404, response.text)

    def test_read_one(self):
        self.should("get a single collection with all expected properties")
        response = client.get(f"/collections/{self.collection.id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))

    def test_create(self):
        name = "New Collection"
        self.should("create a new collection")
        response = client.post("/collections/", json=dict(name=name, description=name))
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that collection has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["name"], name)

        self.should("check that collection is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("cleanup")
        delete_test_collection(self.db, data["id"])

    def test_update_not_owned(self):
        self.should("not allow updating not owned collection")
        new_name = "New Collection"
        response = client.patch(f"/collections/{self.collection.id}", json=dict(name=new_name))
        self.assertEqual(response.status_code, 403, response.text)

    def test_update_non_existent(self):
        self.should("not allow updating non-existent collection")
        new_name = "New Collection"
        response = client.patch(f"/collections/non-existent", json=dict(name=new_name))
        self.assertEqual(response.status_code, 404, response.text)

    def test_update_owned(self):
        old_name = "Old Collection Title"
        new_name = "New Collection Title"
        self.should("create a collection with initial properties")
        response = client.post("/collections/", json=dict(name=old_name, description=old_name))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertEqual(data["name"], old_name)

        self.should("patch a collection with new values")
        response = client.patch(f"/collections/{data['id']}", json=dict(name=new_name, description=new_name))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["name"], new_name)
        self.assertEqual(data["description"], new_name)

        self.should("cleanup")
        delete_test_collection(self.db, data["id"])

    def test_update_access(self):
        self.should("create a test collection")
        response = client.post("/collections/", json=dict(name="test", description="test"))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)

        self.should("update an owned test collection access")
        response = client.put(f"/collections/{data['id']}/access", json=dict(user_id=self.user.id, can_view=True, can_edit=True, can_delete=True))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["accessibles"][0]["canView"], True)
        self.assertEqual(data["accessibles"][0]["canEdit"], True)
        self.assertEqual(data["accessibles"][0]["canDelete"], True)

        self.should("cleanup")
        delete_test_collection(db=self.db, id=data["id"])

    def test_update_access_not_owned(self):
        self.should("not update not owned collection access")
        response = client.put(f"/collections/{self.collection.id}/access", json=dict(user_id=self.user.id, can_view=True, can_edit=True, can_delete=True))
        self.assertEqual(response.status_code, 403, response.text)

    def test_update_access_non_existent(self):
        self.should("not update non-existent collection access")
        response = client.put(f"/collections/non-existent/access", json=dict(user_id=self.user.id, can_view=True, can_edit=True, can_delete=True))
        self.assertEqual(response.status_code, 404, response.text)

    def test_delete(self):
        name = "Delete Collection"
        self.should("delete collection")
        response = client.post("/collections/", json=dict(name=name, description=name))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        response = client.delete(f"/collections/{data['id']}")
        self.assertEqual(response.status_code, 200, response.text)

    def test_delete_not_owned(self):
        self.should("not delete not owned collection")
        response = client.delete(f"/collections/{self.collection.id}")
        self.assertEqual(response.status_code, 403, response.text)

    def test_delete_non_existent(self):
        self.should("not delete not existent collection")
        response = client.delete(f"/collections/non-existent")
        self.assertEqual(response.status_code, 404, response.text)

    def test_like(self):
        self.should("like collection")
        response = client.put(f"/collections/{self.collection.id}/like?liked={True}")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertIn("likables", data)
        likables = data["likables"]
        likable = next((item for item in likables if item["userId"] == self.user.id), None)
        self.assertIsNotNone(likable)
        self.assertTrue(likable["liked"])

    def test_like_non_existent(self):
        self.should("fail to like non-existent collection")
        response = client.put(f"/collections/non-existent/like?liked={True}")
        self.assertEqual(response.status_code, 404, response.text)

    def test_unlike(self):
        self.should("unlike collection")
        response = client.put(f"/collections/{self.collection.id}/like?liked={False}")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertIn("likables", data)
        likables = data["likables"]
        likable = next((item for item in likables if item["userId"] == self.user.id), None)
        self.assertIsNotNone(likable)
        self.assertFalse(likable["liked"])

    def test_invalid_body(self):
        self.should("fail on wrong body params")
        response = client.post("/collections/", json=dict(name={"bad": "bad"}, description=False))
        self.assertEqual(response.status_code, 422)
