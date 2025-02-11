# FoxEngine Documentation

## Overview

FoxEngine is a web application that allows you to upload and manage data files. It provides a user-friendly interface for uploading CSV and JSON files, and for searching, managing and exporting the uploaded data.

## User Management

FoxEngine uses a simple user management system. Users can be added and removed by the admin user using the `user_manager.py` script.

### Adding a new user

To add a new user, run the `user_manager.py` script with the `add` command. For example:

```bash
python user_manager.py add --username "newuser" --password "password"
```

### Removing a user

To remove a user, run the `user_manager.py` script with the `remove` command. For example:

```bash
python user_manager.py remove --username "newuser"
```

### Listing users

To list all users, run the `user_manager.py` script with the `list` command. For example:

```bash
python user_manager.py list
```

...

## API

### Upload Data

It's impossible to have perfect csv parsing, some compromises must be made.

Any delimiter can be used, but it must be a single character and not a space or tab.

If the delimiter is present in a field, the field should be inside quotes ( " " ).

If a field contains many values (array), the field should be inside double quotes ( " " ) and the values should be separated by a █ character.
