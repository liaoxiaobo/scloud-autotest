#!/bin/bash

# 检查参数个数
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <disk> <mount_point> <partition> [update_fstab]"
    echo "<partition> should be 'True' or 'False'"
    echo "[update_fstab] should be 'True' or 'False' (default: 'False')"
    exit 1
fi

# 获取参数
DISK=$1
MOUNT_POINT=$2
PARTITION=$3
UPDATE_FSTAB=${4:-False}  # 默认为 False

# 检查磁盘是否存在
if [ ! -b "$DISK" ]; then
    echo "Error: Disk $DISK does not exist."
    exit 1
fi

# 创建挂载点目录（如果不存在）
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Creating mount point directory $MOUNT_POINT"
    mkdir -p "$MOUNT_POINT"
fi

# 取消挂载磁盘（如果已挂载）
if mount | grep "$DISK" > /dev/null; then
    echo "Unmounting $DISK"
    umount "$DISK"
fi

# 如果需要分区和格式化
if [ "$PARTITION" = "True" ]; then
    # 创建分区表
    echo "Creating partition table on $DISK"
    parted -s "$DISK" mklabel gpt

    # 创建一个新的主分区
    echo "Creating a new primary partition on $DISK"
    parted -s -a optimal "$DISK" mkpart primary 0% 100%

    # 获取新分区名称（假设只有一个分区）
    PARTITION_NAME="${DISK}1"

    # 等待分区设备可用
    while [ ! -b "$PARTITION_NAME" ]; do
        sleep 1
    done

    # 格式化分区
    echo "Formatting $PARTITION_NAME with ext4 filesystem"
    mkfs -t "ext4" "$PARTITION_NAME"
else
    PARTITION_NAME="${DISK}1"
fi

# 挂载分区
echo "Mounting $PARTITION_NAME to $MOUNT_POINT"
mount "$PARTITION_NAME" "$MOUNT_POINT"

# 根据参数决定是否更新 /etc/fstab
if [ "$UPDATE_FSTAB" = "True" ]; then
    echo "Updating /etc/fstab"
    UUID=$(blkid -s UUID -o value "$PARTITION_NAME")
    FSTAB_ENTRY="UUID=$UUID $MOUNT_POINT ext4 defaults 0 2"

    # 检查 /etc/fstab 中是否已经存在 MOUNT_POINT
    if grep -q "$MOUNT_POINT" /etc/fstab; then
        echo "Mount point $MOUNT_POINT already exists in /etc/fstab, updating entry."
        sed -i "\|$MOUNT_POINT|d" /etc/fstab
    fi

    echo "$FSTAB_ENTRY" >> /etc/fstab
    echo "/etc/fstab updated."
else
    echo "Skipping /etc/fstab update."
fi

echo "Disk $DISK partitioned (if requested), formatted as ext4, and mounted to $MOUNT_POINT successfully."

exit 0


