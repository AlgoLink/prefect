from pathlib import Path

import pytest

from prefect.tasks.files import Copy, Move, Remove


class TestMove:
    def test_initialization(self):
        m = Move(source_path="source", target_path="target")
        assert m.source_path == "source"
        assert m.target_path == "target"

        m = Move()
        assert m.source_path == ""
        assert m.target_path == ""

    def test_source_path_not_provided(self, tmpdir):
        m = Move()
        with pytest.raises(ValueError, match="No `source_path` provided"):
            m.run()

    def test_target_path_not_provided(self, tmpdir):
        m = Move(source_path="lala")
        with pytest.raises(ValueError, match="No `target_path` provided"):
            m.run()

    def test_run_move_file_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        m = Move(str(source), str(tmpdir))
        res = m.run()
        exp = tmpdir.join("test")
        assert res == Path(str(exp))
        assert exp.exists()
        assert not source.exists()

    def test_run_move_file_to_file(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        target = tmpdir.join("out")

        m = Move(str(source), str(target))
        res = m.run()
        assert res == Path(str(target))
        assert target.exists()
        assert not source.exists()

    def test_run_move_directory_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").mkdir("test")

        m = Move(str(source), str(tmpdir))
        res = m.run()
        exp = tmpdir.join("test")
        assert res == Path(str(exp))
        assert exp.exists()
        assert exp.isdir()
        assert not source.exists()


class TestCopy:
    def test_initialization(self):
        c = Copy(source_path="source", target_path="target")
        assert c.source_path == "source"
        assert c.target_path == "target"

        c = Copy()
        assert c.source_path == ""
        assert c.target_path == ""

    def test_source_path_not_provided(self, tmpdir):
        c = Copy()
        with pytest.raises(ValueError, match="No `source_path` provided"):
            c.run()

    def test_target_path_not_provided(self, tmpdir):
        c = Copy(source_path="lala")
        with pytest.raises(ValueError, match="No `target_path` provided"):
            c.run()

    def test_run_copy_file_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        c = Copy(str(source), str(tmpdir))
        res = c.run()
        exp = tmpdir.join("test")
        assert res == Path(str(exp))
        assert exp.exists()
        assert Path(str(exp)).is_file()
        assert source.exists()

    def test_run_copy_file_to_file(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        target = tmpdir.join("out")

        c = Copy(str(source), str(target))
        res = c.run()
        assert res == Path(str(target))
        assert target.exists()
        assert Path(str(target)).is_file()
        assert source.exists()

    def test_run_copy_directory_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").mkdir("test")

        c = Copy(str(source), tmpdir.join("test2"))
        res = c.run()
        exp = tmpdir.join("test2")
        assert res == Path(str(exp))
        assert exp.exists()
        assert exp.isdir()
        assert source.exists()


class TestRemove:
    def test_initialization(self):
        r = Remove(remove_path="rmdir")
        assert r.remove_path == "rmdir"

        r = Remove()
        assert r.remove_path == ""

    def test_remove_path_not_provided(self, tmpdir):
        r = Remove()
        with pytest.raises(ValueError, match="No `remove_path` provided"):
            r.run()

    def test_remove_file(self, tmpdir):
        source = tmpdir.mkdir("source").join("testfile")
        source.write_binary(b"test")
        assert source.exists()

        Remove(remove_path=source).run()
        assert not source.exists()

    def test_remove_directory(self, tmpdir):
        source = tmpdir.mkdir("source")
        assert source.exists()

        Remove(remove_path=source).run()
        assert not source.exists()
