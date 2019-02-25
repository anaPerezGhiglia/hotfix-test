#!/bin/bash
set -x

function get_next_dev_version () {
    local v=$1
    # Get the last number. First remove any suffixes (such as '-SNAPSHOT').
    local cleaned=`echo $v | sed -e 's/[^0-9][^0-9]*$//'`
    local last_num=`echo $cleaned | sed -e 's/[0-9]*\.//g'`
    local next_num=$(($last_num+1))
    # Finally replace the last number in version string with the new one.
    local stripped=`echo $v | sed -e 's/[0-9][0-9]*\([^0-9]*\)$/'"$next_num"'/'`
    v=$stripped"-SNAPSHOT"
    echo $v
}

# Get release candidate branch name. Assume there is only one
RELEASE_BRANCH_NAME=$(git branch -r | grep "origin/release" | awk '{ sub(/origin\/release\//,""); print }')

if [ -z $RELEASE_BRANCH_NAME ]; then 
    echo "No release candidate branch found"; 
    exit 1;
fi

# Trim trailing spaces
RELEASE_BRANCH_NAME=$(sed -e 's/^[[:space:]]*//' <<<"$RELEASE_BRANCH_NAME")

NEXT_DEV_VERSION=$(get_next_dev_version $RELEASE_BRANCH_NAME)

# Close the branch. Merge to develop and master (don't take off the hyphens!!)
git checkout master
git pull origin master
git checkout release/$RELEASE_BRANCH_NAME
git pull origin release/$RELEASE_BRANCH_NAME

rosie release $RELEASE_BRANCH_NAME
git commit -am "CHANGELOG: release version $RELEASE_BRANCH_NAME"
git push origin release/$RELEASE_BRANCH_NAME  

git checkout master
git merge -s recursive -X theirs release/$RELEASE_BRANCH_NAME
git push origin master

git tag -a $RELEASE_BRANCH_NAME -m "Version "$RELEASE_BRANCH_NAME
git push origin $RELEASE_BRANCH_NAME

git checkout develop
git pull origin develop
git merge --no-ff release/$RELEASE_BRANCH_NAME
git push origin develop

git checkout master
git pull origin master

echo 'start publish '
sbt publish
echo 'finish publish'

git pull origin master

echo "Bumping version number on develop"
git checkout develop
git pull origin develop
sed -i "s/app.version\s*=\s*\".*\"/app.version = \"$NEXT_DEV_VERSION\"/g" conf/application.conf
git commit -am "[finish-release] develop prepared for next dev iteration: $NEXT_DEV_VERSION"
git push origin develop

git branch -D release/$RELEASE_BRANCH_NAME
git push origin :release/$RELEASE_BRANCH_NAME
