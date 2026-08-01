from database import add_mapping, get_mapping, delete_mapping


def save_mapping(src_chat, src_msg, dst_chat, dst_msg, group_id=None):
    add_mapping(src_chat, src_msg, dst_chat, dst_msg, group_id)


def find_mapping(src_chat, src_msg):
    return get_mapping(src_chat, src_msg)


def remove_mapping(src_chat, src_msg):
    delete_mapping(src_chat, src_msg)
