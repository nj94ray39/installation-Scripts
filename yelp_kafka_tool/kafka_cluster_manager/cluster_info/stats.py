"""This files contains supporting api's required to evaluate stats of the
cluster at any given time.
"""
from collections import OrderedDict
from math import sqrt


def get_partitions_per_broker(brokers):
    """Return partition count for each broker."""
    partitions_per_broker = dict(
        (broker, len(broker.partitions))
        for broker in brokers
    )
    return OrderedDict(
        sorted(partitions_per_broker.items(), key=lambda x: x[0].id)
    )


def get_leaders_per_broker(brokers, partitions):
    """Return count for each broker the number of times
    it is assigned as preferred leader.
    """
    leaders_per_broker = dict(
        (broker, 0)
        for broker in brokers
    )
    for partition in partitions:
        leaders_per_broker[partition.leader] += 1
    return leaders_per_broker


# Get imbalance stats
def standard_deviation(data):
    avg_data = sum(data) / len(data)
    variance = map(lambda x: (x - avg_data) ** 2, data)
    avg_variance = sum(variance) / len(data)
    return sqrt(avg_variance)


def get_net_imbalance(count_per_broker):
    """Calculate and return net imbalance based on given count of
    partitions or leaders per broker.

    Net-imbalance in case of partitions implies total number of
    extra partitions from optimal count over all brokers.
    This is also implies, the minimum number of partition movements
    required for overall balancing.

    For leaders, net imbalance implies total number of extra brokers
    as leaders from optimal count.
    """
    net_imbalance = 0
    opt_count = sum(count_per_broker) // len(count_per_broker)
    more_opt_count_allowed = sum(count_per_broker) % len(count_per_broker)
    for count in count_per_broker:
        if count > opt_count:
            if more_opt_count_allowed > 0:
                more_opt_count_allowed -= 1
                net_imbalance += (count - opt_count - 1)
            else:
                net_imbalance += (count - opt_count)
    return net_imbalance


# Get imbalance stats
def get_replication_group_imbalance_stats(rgs, partitions):
    """Calculate same replica count over each replication-group.
    Can only be calculated on current cluster-state.
    """
    same_replica_per_rg = dict((rg_id, 0) for rg_id in rgs.keys())

    # Get broker-id to rg-id map
    broker_rg_id = {}
    for rg in rgs.itervalues():
        for broker in rg.brokers:
            broker_rg_id[broker.id] = rg.id

    # Evaluate duplicate replicas count in each replication-group
    for partition in partitions.itervalues():
        rg_ids = []
        for broker in partition.replicas:
            rg_id = broker_rg_id[broker.id]
            # Duplicate replica found
            if rg_id in rg_ids:
                same_replica_per_rg[rg_id] += 1
            else:
                rg_ids.append(rg_id)
    net_imbalance = sum(same_replica_per_rg.values())

    # Adjust imbalance to ignore duplicate replicas with
    # replication-factor greater than #replication-groups
    rg_count = len(rgs)
    for partition in partitions.itervalues():
        replication_factor = len(partition.replicas)
        if replication_factor > rg_count:
            net_imbalance -= (replication_factor - rg_count)
    return net_imbalance, same_replica_per_rg


def get_leader_imbalance_stats(brokers, partitions):
    leaders_per_broker = get_leaders_per_broker(
        brokers.itervalues(),
        partitions.itervalues(),
    )

    # Calculate standard deviation of leader imbalance
    stdev_imbalance = standard_deviation(leaders_per_broker.values())

    # Calculation net imbalance
    net_imbalance = get_net_imbalance(leaders_per_broker.values())
    return stdev_imbalance, net_imbalance, leaders_per_broker


def get_topic_imbalance_stats(rgs, brokers, topics):
    same_topic_partition_count_per_broker = {}
    for replication_group in rgs.values():
        for broker in replication_group.brokers:
            # Get extra-partition-count of only those topics which has more
            # than 1 partition  in a broker
            partition_count = sum(
                (partition_count - 1) for partition_count in
                broker.get_per_topic_partitions_count().values()
                if partition_count > 1
            )
            if partition_count > 0:
                same_topic_partition_count_per_broker[broker] = \
                    partition_count
    net_imbalance = sum(same_topic_partition_count_per_broker.itervalues())

    # Adjust imbalance due to topics with partitions greater than #brokers
    total_brokers = len(brokers)
    for topic in topics.itervalues():
        if topic.partition_count > total_brokers:
            net_imbalance -= (topic.partition_count - total_brokers)
    return net_imbalance, same_topic_partition_count_per_broker


def get_partition_imbalance_stats(brokers):
    partitions_per_broker = get_partitions_per_broker(brokers.itervalues())

    # Calculate standard deviation of partition imbalance
    stdev_imbalance = standard_deviation(partitions_per_broker.values())
    # Net total imbalance of partition count over all brokers
    net_imbalance = get_net_imbalance(partitions_per_broker.values())
    return stdev_imbalance, net_imbalance, partitions_per_broker
