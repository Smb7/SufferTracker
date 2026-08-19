FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY src/JobTracker.Api/JobTracker.Api.csproj src/JobTracker.Api/
RUN dotnet restore src/JobTracker.Api/JobTracker.Api.csproj
COPY src/JobTracker.Api/ src/JobTracker.Api/
RUN dotnet publish src/JobTracker.Api/JobTracker.Api.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "JobTracker.Api.dll"]
