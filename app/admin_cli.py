"""Explicit server-side recovery of a linked media administrator."""
import argparse
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .main import sync_users,invalidate


def main():
    parser=argparse.ArgumentParser(description='Manage Gatearr media-account administration')
    parser.add_argument('action',choices=['list-users','grant-admin'])
    parser.add_argument('media_id',nargs='?')
    args=parser.parse_args()
    with SessionLocal() as db:
        sync_users(db)
        if args.action=='list-users':
            for user in db.scalars(select(User).where(User.emby_id.is_not(None),User.active.is_(True))):
                print(f'{user.emby_id}\t{user.name}\tadmin={user.admin}')
            return
        if not args.media_id:parser.error('grant-admin requires an existing media user ID')
        user=db.scalar(select(User).where(User.emby_id==args.media_id,User.active.is_(True),User.emby_missing.is_(False)))
        if not user:raise SystemExit('Active media account not found')
        user.admin=True
        invalidate(db,user)
        print('Gatearr administrator granted. Sign in with the usual media-server credentials.')

if __name__=='__main__':main()
