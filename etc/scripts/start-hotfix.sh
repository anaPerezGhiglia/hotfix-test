#!/bin/bash
set -x
HOTFIX_VERSION=$1

git checkout master
git pull origin --prune

opened_branches=$(git branch -r | grep hotfix)
if [ ! -z "$opened_branches" ]; then
    echo "============= ERROR ================="
    echo "There are remote hotfixes already opened"
    echo "Consider closing them"
    echo "Exiting with error"
    echo $opened_branches
    exit 1
fi

CURRENT_VERSION=$(cat conf/application.conf | grep "app.version" | awk -F= '{print $2}' | sed 's/\"//g')
echo "Master version:$CURRENT_VERSION"
echo "Hotfix version:$HOTFIX_VERSION"

git checkout -b "hotfix/$HOTFIX_VERSION" master
sed -i "s/app.version\s*=\s*\".*\"/app.version = \"$HOTFIX_VERSION\"/g" conf/application.conf
git commit -am "Hotfix version number updated to $HOTFIX_VERSION"
git push origin hotfix/$HOTFIX_VERSION

echo "Do the fix on branch hotfix/"$HOTFIX_VERSION

echo
echo "Done"
