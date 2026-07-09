from permissions import can_read_bank, can_write_bank, Bank, User

class TestPermissions:
    def test_public_bank_readable_by_anonymous(self):
        bank = Bank({'owner_id': None, 'visibility': 'public', 'status': 'active'})
        assert can_read_bank(None, bank) is True

    def test_private_bank_owner_can_read(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'active'})
        user = User({'id': 1, 'role': 'student'})
        assert can_read_bank(user, bank) is True

    def test_private_bank_others_cannot_read(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'active'})
        user = User({'id': 2, 'role': 'student'})
        assert can_read_bank(user, bank) is False

    def test_admin_can_read_any_bank(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'active'})
        user = User({'id': 2, 'role': 'admin'})
        assert can_read_bank(user, bank) is True

    def test_hidden_bank_only_admin(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'hidden'})
        user = User({'id': 1, 'role': 'student'})
        assert can_read_bank(user, bank) is False
        admin = User({'id': 2, 'role': 'admin'})
        assert can_read_bank(admin, bank) is True

    def test_write_requires_login(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'active'})
        assert can_write_bank(None, bank) is False

    def test_owner_can_write(self):
        bank = Bank({'owner_id': 1, 'visibility': 'private', 'status': 'active'})
        user = User({'id': 1, 'role': 'student'})
        assert can_write_bank(user, bank) is True
