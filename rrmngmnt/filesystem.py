import os
from rrmngmnt.service import Service
from rrmngmnt import errors


class FileSystem(Service):
    """
    Class for working with filesystem.
    It has same interface as 'os' module.
    """
    def _exec_file_test(self, op, path):
        return self.host.executor().run_cmd(
            ['[', '-%s' % op, path, ']']
        )[0] == 0

    def exists(self, path):
        return self._exec_file_test('e', path)

    def isfile(self, path):
        return self._exec_file_test('f', path)

    def isdir(self, path):
        return self._exec_file_test('d', path)

    def remove(self, path):
        return self.host.executor().run_cmd(
            ['rm', '-f', path]
        )[0] == 0
    unlink = remove

    def rmdir(self, path):
        if path == "/":
            raise ValueError("Attempt to remove root dir '/' !")
        return self.host.executor().run_cmd(
            ['rm', '-rf', path]
        )[0] == 0

    def listdir(self, path):
        return self.host.executor().run_cmd(
            ['ls', '-A1', path]
        )[1].split()

    def touch(self, file_name, path):
        """
        Creates a file on host

        __author__ = "ratamir"
        :param file_name: The file to create
        :type file_name: str
        :param path: The path under which the file will be created
        :type path: str
        :returns: True when file creation succeeds, False otherwise
        False otherwise
        :rtype: bool
        """
        full_path = os.path.join(path, file_name)
        return self.host.run_command(['touch', full_path])[0] == 0

    def read_file(self, path):
        """
        Reads a content of a file in a given path

        :param path: The path from where to take a content from
        :type path: str
        :return: Content of a file
        :rtype: str
        """
        cmd = ["cat", path]
        rc, out, _ = self.host.run_command(cmd)
        return out if not rc else ""

    def create_script(self, content, path):
        """
        Create script on filesystem, and make it executable.

        :param content: content of the script
        :type content: str
        :param path: path to script to create
        :type path: str
        :raises: CommandExecutionFailure when can not change permissions
        """
        executor = self.host.executor()
        with executor.session() as session:
            with session.open_file(path, 'wb') as fh:
                fh.write(content)
            cmd = ["chmod", "+x", path]
            rc, _, err = session.run_cmd(cmd)
            if rc:
                raise errors.CommandExecutionFailure(
                    executor, cmd, rc, err,
                )

    def wget(self, url, f_dir):
            """
            Download file on the host from given url

            :param url: url to file
            :type url: str
            :param f_dir: file directory on host
            :type f_dir: str
            :return: absolute path to file
            :rtype: str
            """
            rc = None
            file_path = os.path.join(f_dir, url.split('/')[-1])
            with self.host.executor().session() as vds_session:
                wget_command = vds_session.command(
                    ['wget', '-O', file_path, url]
                )
                with wget_command.execute() as (_, _, stderr):
                    counter = 0
                    wait_progress = False
                    while rc is None:
                        line = stderr.readline()
                        if counter == 1000 or not wait_progress:
                            counter = 0
                            self.logger.info(line)
                        if 'Saving to' in line:
                            wait_progress = True
                        counter += 1
                        rc = wget_command.get_rc()
            if rc:
                self.logger.error('Failed to download file from url %s', url)
                return ''
            return file_path
