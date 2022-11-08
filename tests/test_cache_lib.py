import json
import subprocess
import os
import shutil
import time
import tempfile
from pathlib import Path

from cache_lib import cacher, iterator_cacher
from cache_lib.cache_lib import (
    get_func_path,
    default_read_cache_f,
    default_write_cache_f,
    default_iterator_read_cache_f,
    default_iterator_write_cache_f,
)


def test_get_func_path():
    def f():
        pass

    assert get_func_path(f) == os.path.realpath(__file__)
    assert os.path.samefile(
        get_func_path(cacher),
        os.path.join(
            os.path.realpath(os.path.dirname(__file__)),
            "..",
            "cache_lib",
            "cache_lib.py",
        ),
    )


def _make_temp_file(path):
    f_contents = str(time.time())
    with open(path, "w") as outf:
        outf.write(f_contents)


def _json_read_cache_f(cache_path):
    with open(cache_path, "r") as inf:
        return json.load(inf)


def _json_write_cache_f(return_value, cache_path):
    with open(cache_path, "w") as outf:
        json.dump(return_value, outf)


def test_cacher():
    for read_f, write_f in (
        (_json_read_cache_f, _json_write_cache_f),
        (default_read_cache_f, default_write_cache_f),
    ):
        temp_dir = tempfile.mkdtemp()
        _, path1 = tempfile.mkstemp()
        _, path2 = tempfile.mkstemp()
        _, kwargpath = tempfile.mkstemp()

        try:
            f_execution_times = {}

            @cacher(
                cache_base=temp_dir, write_cache_f=write_f, read_cache_f=read_f
            )
            def f(path, kwargpath=None):
                f_execution_times[path] = time.time()
                with open(path, "r") as inf:
                    out = inf.read()
                if kwargpath is not None:
                    with open(kwargpath, "r") as inf:
                        out += inf.read()
                return out

            _make_temp_file(path1)
            _make_temp_file(path2)
            _make_temp_file(kwargpath)
            f1_contents = f(path1)
            f2_contents = f(path2, kwargpath=kwargpath)

            # f should execute for path2 as well
            assert path2 in f_execution_times
            assert f_execution_times[path1] != f_execution_times[path2]

            f_last_ran_for_path1 = f_execution_times[path1]
            f_last_ran_for_path2 = f_execution_times[path2]

            # file 1 has not changed, f should not execute
            f1_contents_again = f(path1)
            assert f_execution_times[path1] == f_last_ran_for_path1
            assert f1_contents_again == f1_contents

            # touch file 2, f should execute
            Path(path2).touch()
            touched_f2_contents = f(path2, kwargpath=kwargpath)
            assert f_execution_times[path2] != f_last_ran_for_path2
            assert touched_f2_contents == f2_contents

            f_last_ran_for_path2 = f_execution_times[path2]
            # touch kwargpath, f should execute again
            Path(kwargpath).touch()
            touched_again_f2_contents = f(path2, kwargpath=kwargpath)
            assert f_execution_times[path2] != f_last_ran_for_path2
            assert touched_again_f2_contents == f2_contents

            _make_temp_file(path1)
            changed_f1_contents = f(path1)
            # file 2 has changed, f should execute
            assert f_execution_times[path1] != f_last_ran_for_path1
            assert changed_f1_contents != f1_contents

            # # redefine f without changing it
            # @cacher(cache_base=temp_dir)
            # def f(path):
            #     f_execution_times[path] = time.time()
            #     with open(path, "r") as inf:
            #         return inf.read()

            # # f has not changed, contents should be same
            # redefined_f1_contents = f(path1)
            # assert f_execution_times[path1] == f_last_ran_for_path1
            # assert redefined_f1_contents == f1_contents

            # redefine f and change it
            @cacher(
                cache_base=temp_dir, write_cache_f=write_f, read_cache_f=read_f
            )
            def f(path):
                pointless_statement = None
                f_execution_times[path] = time.time()
                with open(path, "r") as inf:
                    return inf.read()

            changed_f_f1_contents = f(path1)
            assert f_execution_times[path1] != f_last_ran_for_path1
            assert changed_f_f1_contents != f1_contents
        finally:
            os.remove(path1)
            os.remove(path2)
            os.remove(kwargpath)
            shutil.rmtree(temp_dir)


def _json_iterator_read_cache_f(cache_path):
    with open(cache_path, "r") as inf:
        for line in inf:
            yield json.loads(line)


def _json_iterator_write_cache_f(values, cache_path):
    with open(cache_path, "w") as outf:
        for value in values:
            json.dump(value, outf)
            outf.write("\n")


def test_iterator_cacher():
    for read_f, write_f in (
        (_json_iterator_read_cache_f, _json_iterator_write_cache_f),
        (default_iterator_read_cache_f, default_iterator_write_cache_f),
    ):
        temp_dir = tempfile.mkdtemp()
        _, path1 = tempfile.mkstemp()
        _, path2 = tempfile.mkstemp()
        _, kwargpath = tempfile.mkstemp()

        try:
            f_execution_times = {}

            @iterator_cacher(
                cache_base=temp_dir, write_cache_f=write_f, read_cache_f=read_f
            )
            def g(path, start_i, stop_i):
                f_execution_times[(path, start_i, stop_i)] = time.time()
                for i in range(start_i, stop_i):
                    yield i

            _make_temp_file(path1)
            # _make_temp_file(path2)
            # _make_temp_file(kwargpath)
            args1 = (path1, 0, 5)
            l1 = list(g(*args1))
            g_last_ran_for_args1 = f_execution_times[args1]
            l1_again = list(g(*args1))
            assert l1 == l1_again
            assert f_execution_times[args1] == g_last_ran_for_args1

            args2 = (path2, 2, 4)
            l2 = list(g(*args2))
            g_last_ran_for_args2 = f_execution_times[args2]
            Path(path2).touch()
            touched_l2 = list(g(*args2))
            assert f_execution_times[args2] != g_last_ran_for_args2
            assert l2 == touched_l2

        finally:
            os.remove(path1)
            os.remove(path2)
            os.remove(kwargpath)
            shutil.rmtree(temp_dir)


def test_cacher_across_runs():
    temp_dir = tempfile.mkdtemp()
    _, path = tempfile.mkstemp()
    try:

        def _bool_from_out(subprocess_out):
            contents = (
                subprocess_out.stdout.decode().strip().rsplit("\n", maxsplit=1)
            )
            if len(contents) == 2:
                print(contents[0])
                bool_str = contents[1]
            else:
                bool_str = contents[0]
            if not bool_str in ("True", "False"):
                raise ValueError()
            return eval(bool_str)

        Path(path).touch()
        helper_script = os.path.join(
            os.path.dirname((os.path.realpath(__file__))), "cache_helper.py"
        )
        result = _bool_from_out(
            subprocess.run(
                ["python3", helper_script, temp_dir, path],
                capture_output=True,
                check=True,
            )
        )
        assert result
        result = _bool_from_out(
            subprocess.run(
                ["python3", helper_script, temp_dir, path],
                capture_output=True,
                check=True,
            )
        )
        assert not result
        Path(helper_script).touch()
        result = _bool_from_out(
            subprocess.run(
                ["python3", helper_script, temp_dir, path],
                capture_output=True,
                check=True,
            )
        )
        assert result
    finally:
        os.remove(path)
        shutil.rmtree(temp_dir)
