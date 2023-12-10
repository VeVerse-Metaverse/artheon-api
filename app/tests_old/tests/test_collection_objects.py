from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.tests_old.base import TestCaseBase, login
from app.tests_old.client import client

expected_properties = ["id", "objectId", "collectionId", "position", "rotation", "scale", "visible"]


def create_test_collection(db: Session) -> models.Collection:
    collection = schemas.CollectionCreate(name="Test Collection", description="Test Collection")
    return crud.collection.create(db, entity=collection)


def create_test_object(db: Session) -> models.Object:
    object = schemas.ObjectCreate(name="Test Collection", description="Test Collection", artist="Test", date="1900")
    return crud.object.create(db, entity=object)


def create_test_collection_object(db: Session) -> models.CollectionObject:
    collection_object = schemas.CollectionObjectCreate()
    return crud.collection_object.create(db, source_object=collection_object)


def delete_test_collection(db: Session, id) -> None:
    db.query(models.Collection).filter(models.Collection.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


def delete_test_collection_object(db: Session, id) -> None:
    db.query(models.CollectionObject).filter(models.CollectionObject.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


def delete_test_object(db: Session, id) -> None:
    db.query(models.Object).filter(models.Object.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


class CollectionObjectTestCase(TestCaseBase):
    db: Session
    collection: models.Collection
    object: models.Object
    collection_object: models.CollectionObject

    @classmethod
    def setUpClass(cls) -> None:
        super(CollectionObjectTestCase, cls).setUpClass()
        login()
        cls.collection = create_test_collection(cls.db)
        cls.object = create_test_object(cls.db)
        cls.collection_object = create_test_collection_object(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        super(CollectionObjectTestCase, cls).tearDownClass()
        delete_test_collection_object(cls.db, cls.collection_object.id)
        delete_test_object(cls.db, cls.object.id)
        delete_test_collection(cls.db, cls.collection.id)

    def test_read_all(self):
        self.should("get a list of more than zero collection objects")
        response = client.get(f"/collections/{self.collection.id}/objects")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertGreater(len(data), 0)

    def test_read_non_existent(self):
        self.should("get error reading non-existent collection object")
        response = client.get(f"/collection-objects/non-existent")
        self.assertEqual(response.status_code, 404, response.text)

    def test_read_one(self):
        self.should("get a single collection object with all expected properties")
        response = client.get(f"/collection-objects/{self.collection_object.id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties), set(expected_properties) - set(data))

    def test_add_to_not_owned_collection(self):
        self.should("not add an object to not owned collection")
        response = client.post(f"/collections/{self.collection.id}/objects/{self.object.id}", json=dict())
        self.assertEqual(response.status_code, 403, response.text)

    def test_add_to_owned_collection(self):
        name = "New Collection Test"
        self.should("create a new collection")
        response = client.post("/collections/", json=dict(name=name, description=name))
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that collection has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertEqual(data["name"], name)
        collection_id = data["id"]

        self.should("check that collection is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("add a new collection object to owned collection")
        response = client.post(f"/collections/{collection_id}/objects/{self.object.id}", json=dict())
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that the collection object has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties), set(expected_properties) - set(data))

        self.should("check that collection object is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("cleanup")
        delete_test_collection_object(self.db, data["id"])
        delete_test_collection(self.db, collection_id)

    def test_update_not_owned(self):
        self.should("not allow updating not owned collection object")
        response = client.patch(f"/collection-objects/{self.collection_object.id}", json=dict(visible=False))
        self.assertEqual(response.status_code, 403, response.text)

    def test_update_non_existent(self):
        self.should("not allow updating non-existent collection")
        response = client.patch(f"/collection-objects/non-existent", json=dict(visible=False))
        self.assertEqual(response.status_code, 404, response.text)

    def test_update_owned(self):
        name = "New Collection Test"
        self.should("create a new collection")
        response = client.post("/collections/", json=dict(name=name, description=name))
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that collection has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertEqual(data["name"], name)
        collection_id = data["id"]

        self.should("check that collection is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("add a new collection object to owned collection")
        response = client.post(f"/collections/{collection_id}/objects/{self.object.id}", json=dict())
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that the collection object has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties), set(expected_properties) - set(data))

        self.should("check that collection object is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("patch a collection object with new values")
        response = client.patch(f"/collection-objects/{data['id']}", json=dict(visible=False))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["visible"], False)

        self.should("cleanup")
        delete_test_collection_object(self.db, data["id"])

    def test_update_access(self):
        name = "New Collection Test"
        self.should("create a new collection")
        response = client.post("/collections/", json=dict(name=name, description=name))
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that collection has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertEqual(data["name"], name)
        collection_id = data["id"]

        self.should("check that collection is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("add a new collection object to owned collection")
        response = client.post(f"/collections/{collection_id}/objects/{self.object.id}", json=dict())
        self.assertEqual(response.status_code, 200, response.text)

        self.should("check that the collection object has been created")
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties), set(expected_properties) - set(data))

        self.should("check that collection object is owned by user who created it")
        accessibles = data["accessibles"]
        accessible = next((item for item in accessibles if item["userId"] == self.user.id and item["isOwner"] is True), None)
        self.assertIsNotNone(accessible)

        self.should("update an owned test collection object access")
        response = client.put(f"/collection-objects/{data['id']}/access", json=dict(user_id=self.user.id, can_view=True, can_edit=True, can_delete=True))
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
