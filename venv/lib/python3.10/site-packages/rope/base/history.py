from rope.base import change, exceptions, taskhandle, utils


class History:
    """A class that holds project history"""

    def __init__(self, project, maxundos=None):
        self.project = project
        self._undo_list = []
        self._redo_list = []
        self._maxundos = maxundos
        self._load_history()
        self.project.data_files.add_write_hook(self.write)
        self.current_change = None

    def _load_history(self):
        if self.save:
            result = self.project.data_files.read_data("history")
            if result is not None:
                to_change = change.DataToChange(self.project)
                for data in result[0]:
                    self._undo_list.append(to_change(data))
                for data in result[1]:
                    self._redo_list.append(to_change(data))

    def do(self, changes, task_handle=taskhandle.DEFAULT_TASK_HANDLE):
        """Perform the change and add it to the `self.undo_list`

        Note that uninteresting changes (changes to ignored files)
        will not be appended to `self.undo_list`.

        """
        try:
            self.current_change = changes
            changes.do(change.create_job_set(task_handle, changes))
        finally:
            self.current_change = None
        if self._is_change_interesting(changes):
            self.undo_list.append(changes)
            self._remove_extra_items()
        del self.redo_list[:]

    def _remove_extra_items(self):
        if len(self.undo_list) > self.max_undos:
            del self.undo_list[0 : len(self.undo_list) - self.max_undos]

    def _is_change_interesting(self, changes):
        for resource in changes.get_changed_resources():
            if not self.project.is_ignored(resource):
                return True
        return False

    def undo(self, change=None, drop=False, task_handle=taskhandle.DEFAULT_TASK_HANDLE):
        """Redo done changes from the history

        When `change` is `None`, the last done change will be undone.
        If change is not `None` it should be an item from
        `self.undo_list`; this change and all changes that depend on
        it will be undone.  In both cases the list of undone changes
        will be returned.

        If `drop` is `True`, the undone change will not be appended to
        the redo list.

        """
        if not self._undo_list:
            raise exceptions.HistoryError("Undo list is empty")
        if change is None:
            change = self.undo_list[-1]
        dependencies = self._find_dependencies(self.undo_list, change)
        self._move_front(self.undo_list, dependencies)
        self._perform_undos(len(dependencies), task_handle)
        result = self.redo_list[-len(dependencies) :]
        if drop:
            del self.redo_list[-len(dependencies) :]
        return result

    def redo(self, change=None, task_handle=taskhandle.DEFAULT_TASK_HANDLE):
        """Redo undone changes from the history

        When `change` is `None`, the last undone change will be
        redone.  If change is not `None` it should be an item from
        `self.redo_list`; this change and all changes that depend on
        it will be redone.  In both cases the list of redone changes
        will be returned.

        """
        if not self.redo_list:
            raise exceptions.HistoryError("Redo list is empty")
        if change is None:
            change = self.redo_list[-1]
        dependencies = self._find_dependencies(self.redo_list, change)
        self._move_front(self.redo_list, dependencies)
        self._perform_redos(len(dependencies), task_handle)
        return self.undo_list[-len(dependencies) :]

    def _move_front(self, change_list, changes):
        for change in changes:
            change_list.remove(change)
            change_list.append(change)

    def _find_dependencies(self, change_list, change):
        index = change_list.index(change)
        return _FindChangeDependencies(change_list[index:])()

    def _perform_undos(self, count, task_handle):
        for i in range(count):
            self.current_change = self.undo_list[-1]
            try:
                job_set = change.create_job_set(task_handle, self.current_change)
                self.current_change.undo(job_set)
            finally:
                self.current_change = None
            self.redo_list.append(self.undo_list.pop())

    def _perform_redos(self, count, task_handle):
        for i in range(count):
            self.current_change = self.redo_list[-1]
            try:
                job_set = change.create_job_set(task_handle, self.current_change)
                self.current_change.do(job_set)
            finally:
                self.current_change = None
            self.undo_list.append(self.redo_list.pop())

    def contents_before_current_change(self, file):
        if self.current_change is None:
            return None
        result = self._search_for_change_contents([self.current_change], file)
        if result is not None:
            return result
        if file.exists() and not file.is_folder():
            return file.read()
        else:
            return None

    def _search_for_change_contents(self, change_list, file):
        for change_ in reversed(change_list):
            if isinstance(change_, change.ChangeSet):
                result = self._search_for_change_contents(change_.changes, file)
                if result is not None:
                    return result
            if isinstance(change_, change.ChangeContents) and change_.resource == file:
                return change_.old_contents

    def write(self):
        if self.save:
            data = []
            to_data = change.ChangeToData()
            self._remove_extra_items()
            data.append([to_data(change_) for change_ in self.undo_list])
            data.append([to_data(change_) for change_ in self.redo_list])
            self.project.data_files.write_data("history", data)

    def get_file_undo_list(self, resource):
        return [
            change
            for change in self.undo_list
            if resource in change.get_changed_resources()
        ]

    def __str__(self):
        return "History holds %s changes in memory" % (
            len(self.undo_list) + len(self.redo_list)
        )

    undo_list = property(lambda self: self._undo_list)
    redo_list = property(lambda self: self._redo_list)

    @property
    def tobe_undone(self):
        """The last done change if available, `None` otherwise"""
        if self.undo_list:
            return self.undo_list[-1]

    @property
    def tobe_redone(self):
        """The last undone change if available, `None` otherwise"""
        if self.redo_list:
            return self.redo_list[-1]

    @property
    def max_undos(self):
        if self._maxundos is None:
            return self.project.prefs.get("max_history_items", 100)
        else:
            return self._maxundos

    @property
    def save(self):
        return self.project.prefs.get("save_history", False)

    @property
    @utils.deprecated("compress_history is no longer supported")
    def compress(self):
        return False

    def clear(self):
        """Forget all undo and redo information"""
        del self.undo_list[:]
        del self.redo_list[:]


class _FindChangeDependencies:
    def __init__(self, change_list):
        self.change = change_list[0]
        self.change_list = change_list
        self.changed_resources = set(self.change.get_changed_resources())

    def __call__(self):
        result = [self.change]
        for change in self.change_list[1:]:
            if self._depends_on(change, result):
                result.append(change)
                self.changed_resources.update(change.get_changed_resources())
        return result

    def _depends_on(self, changes, result):
        for resource in changes.get_changed_resources():
            if resource is None:
                continue
            if resource in self.changed_resources:
                return True
            for changed in self.changed_resources:
                if resource.is_folder() and resource.contains(changed):
                    return True
                if changed.is_folder() and changed.contains(resource):
                    return True
        return False
