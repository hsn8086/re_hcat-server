import time

from containers import Group, ReturnData, User, EventContainer
from event.base_event import BaseEvent


class JoinGroup(BaseEvent):
    auth = True

    def _run(self, group_id, add_info):
        ec = EventContainer(self.server.db_event)
        ec. \
            add('type', 'group_join_request'). \
            add('rid', ec.rid). \
            add('group_id', group_id). \
            add('user_id', self.user_id). \
            add('add_info', add_info). \
            add('time', time.time())
        ec.write_in()
        agreed_ec = EventContainer(self.server.db_event)
        agreed_ec. \
            add('type', 'group_join_request_agreed'). \
            add('rid', ec.rid). \
            add('group_id', group_id). \
            add('time', time.time())

        with self.server.open_user(self.user_id) as u:
            user: User = u.value
            user_name = user.user_name
            if group_id in user.groups_dict:
                return ReturnData(ReturnData.ERROR, 'You\'re already in the group.')

        try:
            join_success = False
            with self.server.db_group.enter(group_id) as g:
                group: Group = g.value
                group_name = group.name
                verif_method = group.group_settings['verification_method']
                answer = group.group_settings['answer']
                admin_list = list(group.admin_list) + [group.owner]
                if verif_method == 'fr':
                    agreed_ec.write_in()
                    group.member_dict[self.user_id] = {'nick': user_name}
                    join_success = True
                    return ReturnData(ReturnData.OK)
                elif verif_method == 'aw':
                    if add_info == answer:
                        agreed_ec.write_in()
                        join_success = True
                        return ReturnData(ReturnData.OK)
                    else:
                        return ReturnData(ReturnData.ERROR, 'Wrong answer.')
        finally:  # "finally" has a higher priority than return, so this statement will be executed no matter what.
            if join_success:
                with self.server.open_user(self.user_id) as u:
                    user: User = u.value
                    user.groups_dict = {'remark': group_name, 'time': time.time()}
                    user.add_user_event(agreed_ec)

        if verif_method == 'na':
            return ReturnData(ReturnData.ERROR, 'This group don\'t allow anyone join.')

        elif verif_method == 'ac':
            for admin_id in admin_list:
                # add to admin todo_list
                with self.server.open_user(admin_id) as u:
                    user: User = u.value
                    user.add_user_event(ec)
            return ReturnData(ReturnData.OK, 'Awaiting administrator review.')
