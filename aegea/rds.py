"""
RDS FTW
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, getpass
from datetime import datetime

from . import register_parser
from .util import Timestamp, paginate
from .util.printing import format_table, page_output, get_field, get_cell, tabulate
from .util.aws import ARN, resources, clients

def rds(args):
    rds_parser.print_help()

rds_parser = register_parser(rds, help='Manage RDS resources', description=__doc__,
                             formatter_class=argparse.RawTextHelpFormatter)

def add_tags(resource, prefix, key):
    region = clients.rds.meta.region_name
    account_id = ARN(resources.iam.CurrentUser().user.arn).account_id
    resource_id = ":".join([prefix, resource[key]])
    arn = ARN(region=region, account_id=account_id, service="rds", resource=resource_id)
    resource["tags"] = clients.rds.list_tags_for_resource(ResourceName=str(arn))["TagList"]
    return resource

def ls(args):
    paginator = clients.rds.get_paginator('describe_db_instances')
    table = [add_tags(i, "db", "DBInstanceIdentifier") for i in paginate(paginator)]
    page_output(tabulate(table, args))

parser = register_parser(ls, parent=rds_parser)

def snapshots(args):
    paginator = clients.rds.get_paginator('describe_db_snapshots')
    table = [add_tags(i, "snapshot", "DBSnapshotIdentifier") for i in paginate(paginator)]
    page_output(tabulate(table, args))

parser = register_parser(snapshots, parent=rds_parser)

def create(args):
    tags = dict([tag.split("=", 1) for tag in args.tags])
    clients.rds.create_db_instance(DBInstanceIdentifier=args.name,
                                   AllocatedStorage=args.storage,
                                   DBName=args.name,
                                   Engine=args.engine,
                                   StorageType=args.storage_type,
                                   StorageEncrypted=True,
                                   AutoMinorVersionUpgrade=True,
                                   MultiAZ=False,
                                   MasterUsername=args.master_username or getpass.getuser(),
                                   MasterUserPassword=args.master_user_password,
                                   VpcSecurityGroupIds=args.security_groups,
                                   DBInstanceClass=args.db_instance_class,
                                   Tags=[dict(Key=k, Value=v) for k, v in tags.items()],
                                   CopyTagsToSnapshot=True)
    clients.rds.get_waiter('db_instance_available').wait(DBInstanceIdentifier=args.name)
    instance = clients.rds.describe_db_instances(DBInstanceIdentifier=args.name)["DBInstances"][0]
    return {k: instance[k] for k in ("Endpoint", "DbiResourceId")}

parser = register_parser(create, parent=rds_parser)
parser.add_argument('name')
parser.add_argument('--engine')
parser.add_argument('--storage', type=int)
parser.add_argument('--storage-type')
parser.add_argument('--master-username', '--username')
parser.add_argument('--master-user-password', '--password', required=True)
parser.add_argument('--db-instance-class')
parser.add_argument('--tags', nargs="+", default=[])
parser.add_argument('--security-groups', nargs="+", default=[])

def delete(args):
    clients.rds.delete_db_instance(DBInstanceIdentifier=args.name, SkipFinalSnapshot=True)

parser = register_parser(delete, parent=rds_parser)
parser.add_argument('name')

def snapshot(args):
    raise NotImplementedError()

parser = register_parser(snapshot, parent=rds_parser)

def restore(args):
    tags = dict([tag.split("=", 1) for tag in args.tags])
    clients.rds.restore_db_instance_from_db_snapshot(DBInstanceIdentifier=args.instance_name,
                                                     DBSnapshotIdentifier=args.snapshot_name,
                                                     StorageType=args.storage_type,
                                                     AutoMinorVersionUpgrade=True,
                                                     MultiAZ=False,
                                                     DBInstanceClass=args.db_instance_class,
                                                     Tags=[dict(Key=k, Value=v) for k, v in tags.items()],
                                                     CopyTagsToSnapshot=True)
    clients.rds.get_waiter('db_instance_available').wait(DBInstanceIdentifier=args.instance_name)
    instance = clients.rds.describe_db_instances(DBInstanceIdentifier=args.instance_name)["DBInstances"][0]
    return {k: instance[k] for k in ("Endpoint", "DbiResourceId")}

parser = register_parser(restore, parent=rds_parser)
parser.add_argument('snapshot_name')
parser.add_argument('instance_name')
parser.add_argument('--storage-type')
parser.add_argument('--db-instance-class')
parser.add_argument('--tags', nargs="+", default=[])