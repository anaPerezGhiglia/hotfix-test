#!/bin/bash
#set -x

GIT_MERGE_AUTOEDIT=no
function get_current_version () {
    echo $(cat conf/application.conf | grep "app.version" | awk -F= '{print $2}' | sed 's/\"//g')
}

# Get release candidate branch name. Assume there is only one
RELEASE_BRANCH_NAME=$(git branch -r | grep "origin/hotfix" | awk '{ sub(/origin\/hotfix\//,""); print }')

if [ -z $RELEASE_BRANCH_NAME ]; then 
    echo "No hotfix candidate branch found"; 
    exit 1;
fi

# Trim trailing spaces
RELEASE_VERSION=$(sed -e 's/^[[:space:]]*//' <<<"$RELEASE_BRANCH_NAME")
RELEASE_BRANCH_NAME=hotfix/$RELEASE_VERSION
echo "Hotfix version: $RELEASE_BRANCH_NAME"

#Sanity pulls
git checkout master
git pull origin master
git checkout $RELEASE_BRANCH_NAME
git pull origin $RELEASE_BRANCH_NAME

git checkout master
git merge -s recursive -X theirs $RELEASE_BRANCH_NAME
git push origin master
git tag -a $RELEASE_VERSION -m "Version "$RELEASE_VERSION
git push origin $RELEASE_VERSION

git checkout develop
git pull origin develop
DEVELOP_VERSION=$(get_current_version)
echo "develop version: $DEVELOP_VERSION"
echo "merging into develop"
sleep 3
git merge --no-ff -s recursive -X ours $RELEASE_BRANCH_NAME
echo "*** merging to develop done!"
sed -i "s/app.version\s*=\s*\".*\"/app.version = \"$DEVELOP_VERSION\"/g" conf/application.conf
git add -A
echo "------ returning develop version"
git commit --amend --no-edit
git push origin develop

git checkout master
git pull origin master
#sbt publish

git branch -D $RELEASE_BRANCH_NAME
git push origin :$RELEASE_BRANCH_NAME
