"""One-time, interactive first-admin setup."""
import argparse
from getpass import getpass
from ticket_store import AccessDenied, bootstrap_admin, init_db, reset_bootstrap_password
from local_auth import AuthError

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create or recover the first local admin')
    parser.add_argument('--reset-password', action='store_true', help='Reset the original bootstrap admin password locally')
    parser.add_argument('--username')
    parser.add_argument('--email')
    parser.add_argument('--name')
    args = parser.parse_args()
    if not args.reset_password and not all((args.username, args.email, args.name)):
        parser.error('--username, --email and --name are required when creating an admin')
    first = getpass('Initial password (at least 12 characters): ')
    second = getpass('Confirm password: ')
    if first != second:
        parser.error('Passwords do not match')
    init_db()
    try:
        if args.reset_password:
            reset_bootstrap_password(first)
        else:
            bootstrap_admin(args.username, args.email, first, args.name)
    except (AuthError, AccessDenied) as exc:
        parser.error(str(exc) or 'Admin has already been created')
    print('Password reset. Change it again on first login.' if args.reset_password
          else 'Admin created. Change the initial password on first login.')
