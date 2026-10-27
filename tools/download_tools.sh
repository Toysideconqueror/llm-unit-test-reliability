#!/usr/bin/env bash
# Fetch the Java tooling used by src/java_coverage_runner.py (versions used in the study).
set -euo pipefail
cd "$(dirname "$0")"
MVN=https://repo1.maven.org/maven2
curl -fsSL "$MVN/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar" -o jacocoagent.jar
curl -fsSL "$MVN/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar" -o jacococli.jar
curl -fsSL "$MVN/org/junit/platform/junit-platform-console-standalone/1.11.4/junit-platform-console-standalone-1.11.4.jar" -o junit-platform-console-standalone.jar
ls -l *.jar
