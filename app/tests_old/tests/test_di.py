import inject

from app.tests_old.base import TestCaseBase


class TestService:
    value = 42

    def get_value(self):
        return self.value


class DITestCase(TestCaseBase):
    test_service = inject.attr(TestService)

    def test_inject(self):
        self.should("call injected service method")
        value = self.test_service.get_value()
        self.assertEqual(value, 42)
